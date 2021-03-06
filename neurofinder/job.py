import tempfile
import time
import subprocess
import os
import sys
import json
import importlib
import io
import traceback
from boto.s3.key import Key
from numpy import mean, random, asarray, nanmean

from utils import quiet, printer


class Job(object):
    """
    Class for representing a pull request to validate and execute

    Parameters
    ----------
    pull_req : github.PullRequest.PullRequest
        The pull request to evaluate

    collection : pymongo.collection.Collection
        A mongo collection for storing pull request status

    bucket : S3 bucket
        A bucket on S3 for posting results

    dry : boolean, optional, default = False
        Will run as a dry run if True, skipping messages to github
    """
    def __init__(self, pull_req, collection, bucket, dry=False):
        self.pull_req = pull_req
        self.collection = collection
        self.bucket = bucket
        self.dry = dry

    @property
    def id(self):
        """
        Pull request id
        """
        return self.pull_req.id

    @property
    def login(self):
        """
        Pull request user login
        """
        return self.pull_req.user.login

    @property
    def url(self):
        """
        Pull request repo url for cloning
        """
        return self.pull_req.head.repo.clone_url

    @property
    def branch(self):
        """
        Pull request branch name
        """
        return self.pull_req.head.ref

    def ismergeable(self):
        """
        Check if the pull request is mergeable
        """
        return self.pull_req.mergeable

    def isrecent(self):
        """
        Check if the pull request has been updated since it was last checked
        """
        entry = self.collection.find_one({"id": self.id})
        t0 = entry['last_checked']
        t = self.pull_req.updated_at.utctimetuple()
        updated_at = int(time.mktime(t))
        if t0 < updated_at:
            return True
        else:
            return False

    def isentry(self):
        """
        Check if the pull request is in the collection, otherwise add it
        """
        entry = self.collection.find_one({"id": self.id})
        if not entry:
            printer.status("Adding entry for pull request %s from user %s" % (self.id, self.login))
            payload = {'id': self.id, 'login': self.login, 'validated': False, 'executed': False,
                       'last_checked': 0, 'validated_at': 0, 'executed_at': 0}
            self.collection.insert_one(payload)

    def clear_status(self, status):
        """
        Set status to false for this pull request in the collection
        """
        self.collection.update_one({'id': self.id}, {'$set': {status: False}})

    def check_status(self, status):
        """
        Check status for this pull request in the collection
        """
        entry = self.collection.find_one({"id": self.id})
        return entry[status]

    def update_status(self, status):
        """
        Update the status for this job as successful
        """
        timestamp = int(time.mktime(time.gmtime()))
        self.collection.update_one({"id": self.id}, {"$set": {status: True}})
        self.collection.update_one({"id": self.id}, {"$set": {status + "_at": timestamp}})

    def send_message(self, msg):
        """
        Send a message to the github comment
        """
        printer.status("Sending msg to github: '%s'" % msg)
        if False:
            self.pull_req.create_issue_comment(msg)
        printer.success()

    def update_last_checked(self):
        """
        Update the time this pull request was last checked
        """
        timestamp = int(time.mktime(time.gmtime()))
        self.collection.update_one({"id": self.id}, {"$set": {"last_checked": timestamp}})

    def summarize(self):
        """
        Summarize the submission by parsing various fields
        """
        d = dict()
        d['login'] = self.login
        d['source_url'] = self.url
        d['pull_request'] = self.pull_req.html_url
        d['id'] = self.id
        d['avatar'] = self.pull_req.user.avatar_url
        d['email'] = self.pull_req.user.email

        return d

    def post_image(self, im, folder, filename='sources'):
        """
        Post an image to S3 for this pull request

        Parameters
        ----------
        im : array
            The image as a 2D array (grayscale) or 3D array (RGB)

        name : str
            The folder name to put file in
        """
        from matplotlib.pyplot import imsave, cm

        im = asarray(im)
        imfile = io.BytesIO()
        if im.ndim == 3:
            imsave(imfile, im, format="png")
        else:
            imsave(imfile, im, format="png", cmap=cm.gray)

        k = Key(self.bucket)
        k.key = 'neurofinder/images/' + str(self.id) + '/' + folder + '/' + filename + '.png'
        k.set_contents_from_string(imfile.getvalue())

    def clone(self):
        """
        Clone the repository given for this pull request
        """
        d = tempfile.mkdtemp()

        with quiet():
            subprocess.call(["git", "clone", self.url, d])
            os.chdir(d)
            subprocess.call(["git", "checkout", "-b", self.branch, "origin/%s" % self.branch])

        base = d + '/submissions/%s/' % self.login
        module = base + 'run/'

        return base, module

    def execute(self):
        """
        Execute this pull request
        """
        printer.status("Executing pull request %s from user %s" % (self.id, self.login))

        base, module = self.clone()

        f = open(base + 'info.json', 'r')
        info = json.loads(f.read())

        sys.path.append(module)
        run = importlib.import_module('run')

        spark = os.getenv('SPARK_HOME')
        if spark is None or spark == '':
            raise Exception('must assign the environmental variable SPARK_HOME with the location of Spark')
        sys.path.append(os.path.join(spark, 'python'))
        sys.path.append(os.path.join(spark, 'python/lib/py4j-0.8.2.1-src.zip'))

        from thunder import ThunderContext
        tsc = ThunderContext.start(master="local", appName="neurofinder")

        datasets = ['data-0', 'data-1', 'data-2', 'data-3', 'data-4', 'data-5']
        centers = [5, 7, 9, 11, 13, 15]
        metrics = {'accuracy': [], 'overlap': [], 'distance': [], 'count': [], 'area': []}

        try:
            for ii, name in enumerate(datasets):
                data, ts, truth = tsc.makeExample('sources', dims=(200, 200),
                                                  centers=centers[ii], noise=1.0, returnParams=True)
                sources = run.run(data)

                accuracy = truth.similarity(sources, metric='distance', thresh=10, minDistance=10)
                overlap = truth.overlap(sources, minDistance=10)
                distance = truth.distance(sources, minDistance=10)
                count = sources.count
                area = mean(sources.areas)

                metrics['accuracy'].append({"dataset": name, "value": accuracy})
                metrics['overlap'].append({"dataset": name, "value": nanmean(overlap)})
                metrics['distance'].append({"dataset": name, "value": nanmean(distance)})
                metrics['count'].append({"dataset": name, "value": count})
                metrics['area'].append({"dataset": name, "value": area})

                im = sources.masks(base=data.mean())
                self.post_image(im, name)

            for k in metrics.keys():
                overall = mean([v['value'] for v in metrics[k]])
                metrics[k].append({"dataset": "overall", "value": overall})

            msg = "Execution successful"
            printer.success()
            self.update_status("executed")

        except Exception:
            metrics = None
            msg = "Execution failed"
            printer.error("failed, returning error")
            print(traceback.format_exc())

        self.send_message(msg)

        return metrics, info

    def validate(self):
        """
        Validate this pull request
        """
        printer.status("Validating pull request %s from user %s" % (self.id, self.login))

        base, module = self.clone()

        validated = True
        errors = ""

        if not self.ismergeable():
            validated = False
            errors += "Submission cannot be merged\n"

        if not os.path.isdir(base):
            validated = False
            errors += "Missing directory submissions/%s\n" % self.login
        if not os.path.isfile(base + 'info.json'):
            validated = False
            errors += "Missing info.json\n"
        else:
            try:
                f = open(base + 'info.json', 'r')
                json.loads(f.read())
            except IOError:
                validated = False
                errors += "Cannot find info.json file\n"
            except ValueError:
                validated = False
                errors += "Error parsing info.json file\n"

        if not os.path.isfile(module + 'run.py'):
            validated = False
            errors += "Missing run.py\n"
        if not os.path.isfile(module + '__init__.py'):
            validated = False
            errors += "Missing __init__.py\n"
        else:
            try:
                sys.path.append(module)
                importlib.import_module('run')
            except ImportError:
                validated = False
                errors += "Cannot import run from run.py"

        if validated:
            msg = "Validation successful"
            printer.success()
            self.update_status("validated")
        else:
            msg = "Validation failed:\n" + errors
            printer.error()

        self.send_message(msg)
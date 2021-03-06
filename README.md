# NeuroFinder

[![Join the chat at https://gitter.im/CodeNeuro/neurofinder](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/CodeNeuro/neurofinder?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

Benchmarking platform and competition for source extraction from imaging data

## submit an algorithm (currently in beta testing)
1. Sign up for an account on github (if you don't already have one)
2. Fork this repository
3. Create a branch
4. Add a folder inside `neurofinder/submissions` with the structure described below
5. Submit your branch as a pull request and wait for your algorithm to be validated and run!

Submission structure:
```
neurofinder/submissions/your-user-name/info.json
neurofinder/submissions/your-user-name/run/run.py
neurofinder/submissions/your-user-name/run/__init__.py
```
The file `info.json` should contain the following fields
```
{
    "algorithm": "name of your algorithm",
    "description": "description of your algorithm"
}
```
The file `run.py` should contain a function `run` that accepts as input a Thunder `Images` object and returns a `SourceModel`, and uses Thunder's Source Extraction API to implement the algorithm. The API emphasizes flexibility and modulartiy, allowing for a variety of algorithms. See the existing folder `neurofinder/submissions/example-user/` for an example submission.

Jobs will be automatically run every few days on a dynamically-created Spark cluster, so be patient with your submissions. You will be notified of job status via comments on your pull request.

## data sets
Data sets for evaluating algorithms have been kindly provided by the following individuals and labs:
- Simon Peron & Karel Svoboda / Janelia Research Campus
- Adam Packer, Lloyd Russell, & Michael Hausser / UCL
- (others coming soon...)

All data hosted on Amazon S3 and availiable through the CodeNeuro [data portal](http://datasets.codeneuro.org)

## environment
All jobs will be run on an Amazon EC2 cluster in a standardized environment running Thunder, with the following specs and included libraries:

- Python v2.7.6
- Spark v1.3.0
- Numpy v1.9.2
- Scipy v0.15.1
- Scikit Learn v0.16.1
- Scikit Image v0.10.1
- Matplotlib v1.4.3

as well as several additional libraries included with Anaconda. You can develop and test your code in exactly this environment by following [these instructions](http://thunder-project.org/thunder/docs/install_ec2.html) to launch a cluster on EC2.

## examples
Example notebooks for running source extraction algorithms, on both toy data and real data on S3:
- Loading images and sources for [comparison](http://nbviewer.ipython.org/github/codeneuro/neurofinder/blob/master/notebooks/creating-images-and-sources.ipynb)
- Creating images and sources for [testing](http://nbviewer.ipython.org/github/codeneuro/neurofinder/blob/master/notebooks/loading-images-and-sources.ipynb)

## about the job runner
This repo includes a suite for validating and executing pull requests, storing the status of pull requests in a Mongo database, and outputting the results to a leaderboard. To run its unit tests:
- Install the requirements with `pip install -r /path/to/neurofinder/requirements.txt`
- Call `py.test` inside the base neurofinder directory


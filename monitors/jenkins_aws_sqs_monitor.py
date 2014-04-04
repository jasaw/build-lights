""" jenkins monitor """
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.join(current_dir, "..")
import sys
sys.path.append(parent_dir)

import re

from lib import logger
from lib import list_utils
from lights import job2light_translator


class JenkinsAwsSqsMonitor(object):

    status_dict = {
        'FAILURE' : job2light_translator.STATUS.FAILURE,
        'SUCCESS' : job2light_translator.STATUS.SUCCESS,
        'ABORTED' : job2light_translator.STATUS.ABORTED,
    }

    def __init__(self, jobs, translator, first_job_as_trigger=True):
        self.logger = logger.Logger('JenkinsAwsSqsMonitor')
        self.translator = translator
        self.first_job_as_trigger = first_job_as_trigger
        self.pipeline = jobs
        self.jobs = dict.fromkeys(list(list_utils.flatten_list(jobs)))
        # initialize status to Unknown state
        for name in self.jobs:
            self.jobs[name] = job2light_translator.STATUS.UNKNOWN

    def process_build(self, directive):
        if directive is not None:
            self.__process_directive(directive)
        else:
            return
            # FIXME: we'll lose the previous status if we change the status to POLL_ERROR, don't do that !
            #for name in self.jobs:
            #    self.jobs[name] = job2light_translator.STATUS.POLL_ERROR

        self.logger.log('Jobs: %s', self.jobs)

        for job_name, status in self.jobs.iteritems():
            self.translator.update(job_name, status)



    def __process_directive(self, directive):
        if directive == 'all_off':
            for name in self.jobs:
                self.jobs[name] = job2light_translator.STATUS.DISABLED
            return

        jenkins_regex = r"Build ([A-Z]+): (.*) #"
        match = re.search(jenkins_regex, directive)
        if match is None:
            return
        found_status = match.group(1)
        job_name = match.group(2)

        found_pipeline = list(list_utils.find_list_given_value(self.pipeline, job_name))
        if len(found_pipeline) == 0:
            return
        found_pipeline = found_pipeline[0]
        found_segment_number = found_pipeline.index(job_name)
        if found_status not in JenkinsAwsSqsMonitor.status_dict:
            self.jobs[job_name] = job2light_translator.STATUS.DISABLED
            return

        # set the status for the current job
        self.jobs[job_name] = JenkinsAwsSqsMonitor.status_dict[found_status]

        if self.first_job_as_trigger:
            # use the first job as the indicator of pipeline started
            if found_segment_number == 0:
                for i in range(1, len(found_pipeline)):
                    self.jobs[found_pipeline[i]] = job2light_translator.STATUS.BUILDING_FROM_PREVIOUS_STATE
                return

        index = 0
        if self.first_job_as_trigger:
            index = 1
        if found_segment_number == index and re.match('.*Unit.*', directive):
            # issue found_status to entire pipeline
            for i in range(index, len(found_pipeline)):
                self.jobs[job_name] = JenkinsAwsSqsMonitor.status_dict[found_status]

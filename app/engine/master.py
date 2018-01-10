import random
import tools
from aload import CrowdLoad


class TestMaster(object):
    """A class to distribute load between slaves and make a text description."""
    def __init__(self, test_dict):
        self.actions = list(test_dict['actions'].keys())
        self.duration = sum(test_dict['intervals'])
        self.load = self.transform_load(test_dict)
        self.users = len(tools.load_users())
        self.conf = tools.load_conf()
        self.slaves = sorted([item['host'] for item in self.conf])
        self.part = self.distribute_load()
        self.description = self.describe_test()
        self.test_run_id = tools.generate_test_run_id()

    def describe_test(self):
        description = '\t\t\t\tTOTAL load:\n' + self.describe_load(self.load)
        for slave in self.slaves:
            description += '\t\t\t\tPARTIAL load for Slave %s:\n' % slave
            description += self.describe_load(self.part[slave])
        return description

    def transform_load(self, test_dict):
        # with isinstance(value, int) we check if we have FIXED profile & convert it to normal view:
        load = {key: [value] if isinstance(value, int) else value \
                for key, value in list(test_dict['actions'].items())}
        # now, if we have a RANDOM profile, convert it to normal view:
        test_dict['actions'] = load
        if isinstance(test_dict['actions'][self.actions[0]], dict):
            for action in self.actions:
                tmp = []
                for item in test_dict['actions'][action]:
                    tmp.append(item['sign'] * random.randint(item['left'], item['right']))
                    test_dict['actions'][action] = tmp
        return test_dict

    def distribute_load(self):
        distrib_load = {slave: {'actions': {}, 'intervals': self.load['intervals'], 'users': {}}
                        for slave in self.slaves}
        for action in self.actions:
            same_part = [delta // len(self.slaves) for delta in self.load['actions'][action]]
            residue_part = [delta % len(self.slaves) for delta in self.load['actions'][action]]
            for slave in self.slaves:
                distrib_load[slave]['actions'].update({action: [value for value in same_part]})
            # first slave will take also the residue load
            for i in range(len(residue_part)):
                distrib_load[self.slaves[0]]['actions'][action][i] += residue_part[i]
        i = 0  # used users
        for slave in self.slaves:
            for action in self.actions:
                k = sum([delta for delta in distrib_load[slave]['actions'][action] if delta > 0])
                distrib_load[slave]['users'].update({action: [i, i + k]})
                i += k
        return distrib_load

    def describe_load(self, load):
        description = ''
        users_count = {action: 0 for action in self.actions}
        i = progress = 0
        while i < len(self.load['intervals']):
            description += '%s-th second:\n' % progress
            for action in self.actions:
                delta = load['actions'][action][i]
                users_count.update({action: users_count[action] + delta})
                act = 'added' if delta > 0 else 'removed'
                description += '\tAction "%s": need %s users to be %s, ' % (action, abs(delta), act)
                description += 'total will be %s user(s) doing this action\n' % users_count[action]
            progress += load['intervals'][i]
            i += 1
        description += '\n\t\t\tTechnically, this will be scheduled as follows:'
        for action in self.actions:
            schedule = CrowdLoad('', '', load, action).get_schedule(load['actions'][action],
                                                                    self.load['intervals'], action)
            description += schedule['description']
            description += '\n%s-th second: stop test run.\n' % schedule['duration']
            description += '\nUsers from range [%s, %s) will be taken for %s.\n' % \
                   (load['users'][action][0], load['users'][action][1], action)
        description += '\n%s\n' % ('*' * 100)
        return description

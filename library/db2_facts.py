#!/usr/bin/env python

from __future__ import (absolute_import, division)
__metaclass__ = type

DOCUMENTATION = '''
---
module: db2_facts
version_added: 2.4
short_description: Gather facts of Db2 software and instances
description: 
  - Gather facts of Db2 software and instances
options:
  filter:
    description:
      - Only gather facts about the given choice
    required: false
    default: present
    choices: ["software", "instances", "databases"]

author:
  - ma44in  
'''

EXAMPLES = '''
# Note: 
# Basic fact gathering
- db2_facts:
    filter: software
    
'''

RETURN = '''
---
db2_software_list:
  /opt/IBM/db2/V10.5:
    vrmf: 10.5.0.6
    
  /opt/IBM/db2/V11.1:
    vrmf: 11.1.1.1
    
db2_instance_list
  db2inst1:
    path: /opt/IBM/db2/V11.1.1.1
  db2inst2:
    path: /opt/IBM/db2/V11.5.5.0

db2_database_list
  db2inst1_SAMPLE:
    database_alias: SAMPLE
    database_name: SAMPLE
    instance_name: db2inst1
    instance_path: /opt/IBM/db2/V11.1.1.1

  db2inst2_SAMPLE:
    database_alias: SAMPLE
    database_name: SAMPLE
    instance_name: db2inst2
    instance_path: /opt/IBM/db2/V11.5.5.0
'''

from ansible.module_utils.basic import AnsibleModule
import os
import re

# db2ls output:
#
# # /usr/local/bin/db2ls -c
# #PATH:VRMF:FIXPACK:SPECIAL:INSTALLTIME:INSTALLERUID
# /opt/IBM/db2/V10.5:10.5.0.6:6 :1:Wed Feb  3 15:01:15 2016 CET :0
# /opt/IBM/db2/V10.5_FP7:10.5.0.7:7:1:Wed Feb 15 16:07:21 2017 CET :0
# /opt/IBM/db2/V11.1:11.1.1.1:1 :1:Thu Jul 13 15:28:23 2017 CESTcet :0
#
def get_db2_software_facts(module):
  db2ls_command = os.path.join('/', 'usr', 'local', 'bin', 'db2ls') # /usr/local/bin/db2ls
  software_facts = {}
  
  if os.path.isfile(db2ls_command):
    # Call dbls with '-c' to get colon-seperated output
    db2ls_command = "%s %s" % (db2ls_command, '-c') 
    rc, out, err = module.run_command(db2ls_command)
    if rc == 0:
      for line in out.splitlines(): # e. g. line: /opt/IBM/db2/V10.5:10.5.0.6:6 :1:Wed Feb 3 15:01:15 2016 CET :0"
        if not line.startswith('#'):       
          software_path = line.split(':')[0]
        
          # Add Software to Dict
          software_facts[software_path] = {
            'vrmf' : line.split(':')[1], # Db2 Version e. g.: 10.5.0.6   
            'fixpack' : line.split(':')[2], 
            'special' : line.split(':')[3] 
            #'installtime' : line.split(':')[4], CSV Output broken due to : in date ... 
            #'installeruid' : line.split(':')[5] 
          }

    else:
      module.fail_json(msg="Command %s failed with rc %s\n. stdout: %s\nstderr: %s\n" % (db2ls_command, rc, out, err))

  return software_facts

def get_db2_instance_facts(module):
  instance_facts = {}

  for software_path in get_db2_software_facts(module).keys():
    db2ilist_command = os.path.join(software_path, 'bin', 'db2ilist') # e. g. /opt/ibm/db2/V11.1/bin/db2ilist
 
    if os.path.isfile(db2ilist_command):
      # Get list of db2 instances
      rc, out, err = module.run_command(db2ilist_command)
      if rc == 0:
        for instance in out.splitlines():
          # Add Instance to Dict
          instance_facts[instance] = {
            'path': software_path
          }
      else:
        module.fail_json(msg="Command %s failed with rc %s\n. stdout: %s\nstderr: %s\n" % (db2ilist_command, rc, out, err))
        return
 
  return instance_facts

def get_db2_database_facts(module):
  instance_facts = get_db2_instance_facts(module)
  database_facts = {}
  

  for instance in instance_facts.keys():
    instance_home_dir = os.path.expanduser('~%s' % instance)
    instance_db2profile_path = os.path.join(instance_home_dir, 'sqllib', 'db2profile')
    
    #database_facts[instance] = {}

    if os.path.isfile(instance_db2profile_path):
      command = []

      if os.getuid() != 0:
        command.append("/bin/sudo")

      command.append("/bin/su %s -c" % instance)
      command.append("'. %s; LANG=C db2 list database directory'" % instance_db2profile_path) 
      command = " ".join(command)
  
      # Get Database Directory of Instance
      rc, out, err = module.run_command(command)
      if rc != 0:
        # SQL1057W  The system database directory is empty.  
        # SQL1031N  The database directory cannot be found on the indicated file system.
        if "SQL1057W" in out or "SQL1031N" in out:
          return database_facts # No databases
        else:
          module.fail_json(msg="Command %s failed with rc %s\n. stdout: %s\nstderr: %s\n" % (command, rc, out, err))
          return

      # Parse Output
      # Database 1 entry:
      #   Database alias                       = MWT1
      #   Database name                        = MWT1
      #   Local database directory             = /db2/db2mwtt1/home
      #   Database release level               = 14.00
      #   Comment                              =
      #   Directory entry type                 = Indirect
      database_alias = None
      database_name = None
      for line in out.splitlines():
        if re.match('^ +Database name += .*$', line):
          database_name = line.split('=')[1].strip()
        if re.match('^ +Database alias += .*$', line):
          database_alias = line.split('=')[1].strip()
        if re.match('^ +Directory entry type += Indirect$', line):
          # Local Database found -> Add Database to Dict
          database_facts[instance + "_" + database_name] = {
           'database_name': database_name,
           'database_alias': database_alias,
           'instance_name': instance,
           'instance_path': instance_facts[instance]['path'],
          }
          database_alias = None
          database_name = None

  return database_facts  
 
def main():

  module = AnsibleModule(
             argument_spec = dict(
               filter = dict(default=None, choices=['software', 'instances', 'databases'])
             )
           )

  filter = module.params['filter']

  db2_facts = {}
  
  if not filter or 'software' in filter:
    db2_facts['db2_software_list'] = get_db2_software_facts(module)

  if not filter or 'instances' in filter:
    db2_facts['db2_instance_list'] = get_db2_instance_facts(module)
 
  if not filter or 'databases' in filter:
    db2_facts['db2_database_list'] = get_db2_database_facts(module)
 

  module.exit_json(changed=False, ansible_facts=db2_facts)


def init():
  if __name__ == '__main__':
    return main()

init()
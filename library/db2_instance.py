#!/usr/bin/python

from __future__ import (absolute_import, division)
__metaclass__ = type

# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: db2_instance
version_added: 2.4
short_description: Create, configure or drop a Db2 Instance
description: 
  - Create, configure or drop a Db2 Instance
options:
  name:
    description:
      - name of the Db2 instance to add, configure or drop. If the instance should be 
        created an user with the same name must be created beforehand
    required: true
    
  path:
    description: Path to Db2 Installation directory (e. g. /opt/IBM/db2/10.1)
      - 
    required: true
    default: present

  state:
    description:
      - The database state
    required: false
    default: present
    choices: ["present", "absent"]
    
  port:  
    description:
      - Specifies the port name or number used by the instance. 
    required: false

  type:  
    description:
      - Specifies the type of instance to create.
    required: false
    default: WSE

  auth_type:  
    description:
      - Specifies the authentication type (SERVER, CLIENT or SERVER_ENCRYPT) for the instance.
    required: false
    default: SERVER_ENCRYPT

author:
  - ma44in  
'''

EXAMPLES = '''
# Note: 
# Basic instance creation example
- db2_instance:
    name: db2inst1
    path: /opt/ibm/db2/V11.1
    state: present
'''

from ansible.module_utils.basic import AnsibleModule
import os
import pwd
import re

# db2ls output:
#
# # /usr/local/bin/db2ls -c
# #PATH:VRMF:FIXPACK:SPECIAL:INSTALLTIME:INSTALLERUID
# /opt/IBM/db2/V10.5:10.5.0.6:6 :1:Wed Feb  3 15:01:15 2016 CET :0
# /opt/IBM/db2/V10.5_FP7:10.5.0.7:7:1:Wed Feb 15 16:07:21 2017 CET :0
# /opt/IBM/db2/V11.1:11.1.1.1:1 :1:Thu Jul 13 15:28:23 2017 CESTcet :0
#
def __get_existing_db2_software_paths(module):
    db2ls_command = os.path.join('/', 'usr', 'local', 'bin', 'db2ls') # /usr/local/bin/db2ls
 
    if not os.path.isfile(db2ls_command):
        module.fail_json(msg="Path %s does not exists" % db2ls_command)
        return

    # Get list of db2 software
    software_paths = []
 
    # Call dbls with '-c' to get colon-seperated output
    db2ls_command = "%s %s" % (db2ls_command, '-c') 
    rc, out, err = module.run_command(db2ls_command)
    if rc == 0:
        for line in out.splitlines(): # e. g. line: /opt/IBM/db2/V10.5:10.5.0.6:6 :1:Wed Feb 3 15:01:15 2016 CET :0"
            if line.startswith('/'):
                software_path = line.split(':')[0]
                software_paths.append(software_path)
    else:
        module.fail_json(msg="Command %s failed with rc %s\n. stdout: %s\nstderr: %s\n" % (db2ls_command, rc, out, err))
    
    return software_paths

def __get_existing_instances(module):
    instances = []

    for software_path in __get_existing_db2_software_paths(module):
        db2ilist_command = os.path.join(software_path, 'bin', 'db2ilist') # e. g. /opt/ibm/db2/V11.1/bin/db2ilist
        
        if not os.path.isfile(db2ilist_command):
            module.fail_json(msg="Path %s does not exists" % db2ilist_command)
            return
    
        # Get list of db2 instances
        rc, out, err = module.run_command(db2ilist_command)
        if rc == 0:
            for instance in out.splitlines():
                instances.append(instance)
        else:
            module.fail_json(msg="Command %s failed with rc %s\n. stdout: %s\nstderr: %s\n" % (db2ilist_command, rc, out, err))
            return
    
    return instances

#
# Execute command local
#
# Using db2 command line interface on the host to execute command
#
def __exec_db2_commmand_local(module, instance_name, command):
    # build db2 command line call
    db2_command=[]
    db2_command.append("/bin/sh -c \"")
    db2_command.append("PATH=/bin:/usr/bin . ~%s/sqllib/db2profile;" % instance_name)
    db2_command.append("db2 -tx \\\"%s;\\\"" % command)
    db2_command.append("\"")
    db2_command = " ".join(db2_command)

    return module.run_command(db2_command) # returns: rc, out, err 

def __instance_running(module, instance_name):
    # $ ps -u db2inst1 --no-headers -o comm
    # db2sysc
    # db2vend
    # db2fmp
    # db2fmp
    # #db2vend
    rc, out, err = module.run_command("ps -u %s --no-headers -o comm" % instance_name)

    if err:
      module.fail_json(msg="could not get process list of instance user", err=err) 

    if "db2sysc" in out:
      return True

    return False

def __instance_exists(module, instance_name):
    if instance_name in __get_existing_instances(module):
        return True
    else:
        return False

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name = dict(required=True, type='str'),
            path = dict(required=False, type='str'),
            type = dict(required=False, default='WSE', type='str'),
            port = dict(required=False, type='int'),
            configurations=dict(required=False, default=[], type='list'),
            auth_type = dict(required=False, default='SERVER_ENCRYPT', type='str'),
            state = dict(choices=['present', 'absent'], default='present')
        )
    )

    instance_name = module.params['name']
    software_path = module.params['path']
    instance_port = module.params['port']
    instance_type = module.params['type']
    instance_auth_type = module.params['auth_type']
    configurations = module.params['configurations']
    state = module.params['state']

    # Build db2icrt Command
    has_changed = False
    instance_created = False
    instance_started = False
    db2icrt_command = None

    if state == "present" and not __instance_exists(module, instance_name):
        db2icrt_command = "%s/instance/db2icrt -a %s -s %s -p %s -u %s %s" % (software_path, instance_auth_type, instance_type, instance_port, instance_name, instance_name)
    elif state == "absent" and __instance_exists(module, instance_name):
        db2icrt_command = "%s/instance/db2idrop %s" % (software_path, instance_name)

    # Execute db2icrt command if necessary
    if db2icrt_command:
        rc, out, err = module.run_command(db2icrt_command)

        if rc == 0:
            has_changed=True
            instance_created=True
        else:
            module.fail_json(msg="FAILED COMMAND: %s, RC: %s, STDOUT: %s, STDERR: %s" % (db2icrt_command, rc, out, err))
            return

    # Start Instance if necessary
    if state == "present" and not __instance_running(module, instance_name):
        db2_start_command = "START DATABASE MANAGER"
        rc, out, err = __exec_db2_commmand_local(module, instance_name, db2_start_command)
        
        if rc == 0:
            has_changed=True
            instance_started = True
        else:
            module.fail_json(msg="FAILED COMMAND: %s, RC: %s, STDOUT: %s, STDERR: %s" % (db2_start_command, rc, out, err))
            return
    
    # Read current DBM configuration
    #   $ db2 get dbm cfg
    #   Number of FCM buffers                 (FCM_NUM_BUFFERS) = AUTOMATIC(1024)
    #   FCM buffer size                       (FCM_BUFFER_SIZE) = 32768
    current_configurations = {}
    rc, out, err = __exec_db2_commmand_local(module, instance_name, "GET DBM CFG")
    if rc == 0:
        for line in out.splitlines():
            match = re.match(".* \((.*)\) = (.*)", line)
            
            if match:
                current_configurations[match.group(1).upper()] = match.group(2)
    
    update_dbm_commands = []        
            
    for target_configuration in configurations:
        parameter = target_configuration['name'].upper()
        
        current_value = current_configurations[parameter]   
        target_value = target_configuration['value']        
        target_automatic_flag = target_configuration['automatic'] if 'automatic' in target_configuration else False
        
        if target_automatic_flag is True:                
            if current_value != "AUTOMATIC(%s)" % target_value:
                update_dbm_commands.append("UPDATE DBM CFG USING %s %s AUTOMATIC" % (parameter, target_value))
        else:
            if current_value != "%s" % target_value:
                update_dbm_commands.append("UPDATE DBM CFG USING %s %s" % (parameter, target_value))

    for update_dbm_command in update_dbm_commands:
        rc, out, err = __exec_db2_commmand_local(module, instance_name, update_dbm_command)
        
        if rc == 0:
            has_changed = True
        else:
            module.fail_json(msg="FAILED COMMAND: %s, RC: %s, STDOUT: %s, STDERR: %s" % (update_dbm_command, rc, out, err))

    module.exit_json(changed=has_changed, db2_instance_created=instance_created, db2_instance_started=instance_started, msg="DB2ICRT COMMAND: %s, UPDATE DBM COMMANDS: %s" % (db2icrt_command, update_dbm_commands))

def init():
    if __name__ == '__main__':
        return main()

init()

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
module: db2_command
version_added: 2.4
short_description: Execute db2 command
description: 
  - Execute a db2 command
options:
  instance:
    description:
      - name of the Db2 instance
    required: true
    
  database:
    description:
      -  name of the Db2 database
    required: false
    default: None

  command:
    description:
      - db2 command
    required: true

  file:
    description:
      - path to sql file with db2 commands
    required: true

  logfile:
    description:
      - path where to write logfile
    required: false

  ignorable_sqlcodes:
    description:
      - comma seperated list of sqlcodes to ignore. E. g.: SQL0601N,SQL0579N to ignore sql601 and sql579 errors.
    required: false
  
    
author:
  - ma44in  
'''

EXAMPLES = '''
# Note: 
# Basic db2 command
- db2_command:
    instance: db2inst1
    command: "UPDATE DBM CFG USING DFT_MON_SORT ON"

- db2_command:
    instance: db2inst1
    database: SAMPLE
    command: "select count(*) from syscat.tables"

- db2_command:
    instance: db2inst1
    database: SAMPLE
    file: "/tmp/my_sql_to_create_storagegroups.sql"
    ignorable_sqlcodes: "SQL0601N"
    
- db2_command:
    instance: db2inst1
    database: SAMPLE
    file: "/tmp/my_sql_to_create_storagegroups.sql"
    logfile: "/tmp/output.log"
'''

from ansible.module_utils.basic import AnsibleModule
import os
import pwd
import re

#
# Parse SQLCodes from Db2 CLP Output
#
def __get_sqlcodes_from_db2_output(output):
  # Build dict with sql codes and counts. E. g.: {'0': 3, '-601': 14}
  sqlcodes = {}

  for line in output.splitlines(): 
    # SQL0601N  The name of the object to be created is identical to the existing
    # Extract sqlcode with regex
    match = re.match( r"^(SQL\d+N) .*$", line, re.I)
    if match:
      sqlcode = match.group(1)
      if sqlcode in sqlcodes:
        sqlcodes[sqlcode] += 1
      else:
        sqlcodes[sqlcode] = 1 # Found sqlcode the first time
  
  return sqlcodes


#
# Execute command local
#
# Using db2 command line interface on the host to execute command
#
def __exec_db2_commmand_local(module, instance_name, database_name, command_or_file, logfile=None, ignorable_sqlcodes=None):
    # build db2 command line call
    db2_command=[]
    db2_command.append("/bin/sh -c \"")
    db2_command.append("LANG=C PATH=/bin:/usr/bin . ~%s/sqllib/db2profile;" % instance_name)
    
    if database_name:
      db2_command.append("DB2DBDFT=%s " % database_name)

    if os.path.isfile(command_or_file):
      db2_command.append('db2 -vtxf %s' % command_or_file)
    else:
      db2_command.append("db2 -tx \\\"%s;\\\"" % command_or_file)

    db2_command.append("\"")
    db2_command = " ".join(db2_command)

    # Execute db2 command now
    rc, out, err = module.run_command(db2_command) 

    # Write to Logfile
    if logfile:
      try:
        with open(logfile, "w") as f:
          f.write(out)
          f.close()
      except Exception as e:
        module.warn("Logfile could not be written. Error:" + str(e))
        
    # Check for SQLCodes
    sqlcodes = __get_sqlcodes_from_db2_output(out)

    if ignorable_sqlcodes:
      # Check identified sqlcodes against ignorable_sqlcodes  
      rc = 0
      for sqlcode in sqlcodes:
        if sqlcode in ignorable_sqlcodes or sqlcode == '0':
          continue
        else:     
          rc = 100
      
      if rc > 0:
        err = out
        out = "Found following SQLCODES: %s. Please see STDERR for details." % sqlcodes    

    return (rc, out, err, db2_command)

def main():
    module = AnsibleModule(
        argument_spec = dict(
            instance = dict(required=True, type='str'),
            database = dict(required=False, type='str', default=None),
            command = dict(required=False, type='str', default=None),
            file = dict(required=False, type='str', default=None),
            logfile = dict(required=False, type='str', default=None),
            ignorable_sqlcodes = dict(required=False, type='str', default=None)
        )
    )

    instance_name = module.params['instance']
    database_name = module.params['database']
    command = module.params['command']
    file = module.params['file']
    logfile = module.params['logfile']
    ignorable_sqlcodes = None
    if module.params['ignorable_sqlcodes']:
      ignorable_sqlcodes = module.params['ignorable_sqlcodes'].split(',')

    # Execute command
    if command:
      rc, out, err, generated_command = __exec_db2_commmand_local(module, instance_name, database_name, command, logfile, ignorable_sqlcodes)
    elif file:
      rc, out, err, generated_command = __exec_db2_commmand_local(module, instance_name, database_name, file, logfile, ignorable_sqlcodes)
    else:
      module.fail_json(msg="must specify command or file")
      return
        
    if rc == 0:
        has_changed=True
    else:
        module.fail_json(msg="GENERATED DB2 COMMAND FAILED: %s" % generated_command, rc=rc, stdout=out, stderr=err)
        return
    
    module.exit_json(changed=has_changed, rc=rc, stdout=out, msg="GENERATED DB2 COMMAND: %s" % (generated_command))

def init():
    if __name__ == '__main__':
        return main()

init()

# module_db2

(!) WORK IN PROCESS (See TODO)

Basic modules to manage Db2 instance and databases with native db2 command. 

| Module        | Description
| ------------- | -----------
| db2_facts     | Get facts about installed Db2 Software, Databases or Instances
| db2_instance | Create or drop a Db2 instance
| db2_command | Run a db2 command


## TODO

- Add option to use ibm_db python module
- Convert this to a Ansible collection with tests. Better: Replace this with an offical db2 module from IBM ;-)
- Better Docs

## Usage

Copy module-db2 Folder into Ansible role as follows. See "Embedding Modules and Plugins In Roles" for details. (https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html#id10) 

```sh
.
├── playbook.yml
└── roles
    └── module_db2
        └── library
            ├── db2_command.py
            ├── db2_facts.py
            └── db2_instance.py
```

Use it in a playbook as follows.

```yaml
---
- hosts: all
  roles:
    - role: module_db2
  tasks:
    - name: "Create database in existing instance"
      db2_command:
          instance: "db2inst1"
          command: "CREATE DATABASE SAMPLE"
          ignorable_sqlcodes: "SQL1005N" # SQL1005N: The database alias ... already exists ...
      register: command
      changed_when: "'SQL1005N' not in command.stdout"
```

## Examples

```yaml
---
- hosts: all
  roles:
    - role: module_db2
  tasks:
    - name: "Get db2 database facts"
      db2_facts:
        filter: "databases"
      register: db2_facts

    - name: "Execute SQL in each database"
      db2_command:
        instance: "{{ item.value.instance_name }}"
        database: "{{ item.value.database_name }}"
        command: "SELECT count(*) FROM SYSCAT.TABLES"
      changed_when: False
      loop: "{{  db2_facts.ansible_facts.db2_database_list | dict2items }}"
      register: results

    - debug:
        # Result in stdout like in terminal.
        # TODO: better enable db2_command to execute SQL with ibm_db2 module
        msg: "{{ results }}"
```
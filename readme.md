# Database Backup Utility

This is a Docker container which can be used to set up automated backups for a database.

It uses the `mysqldump` utility to get the data and a python script to do all the heavy lifting. (I find it more flexible than bash.)

## Caveats up Front

This needs to be on the same network as your database, if your database is being run in a Docker container, like mine. You simply need to put this container on the same network. More to follow in the detailed instructions.

There are better ways than `mysqldump`. I don't care; it works and my time is extremely limited.

To do local backups and have them persisted you need to mount a directory into /backups that you'll have access to later. Docker volume, bind mount, whatever.

As for *automation*:

In Linux this is as easy as adding the line `@daily backup_wow` to your [cron jobs](https://www.digitalocean.com/community/tutorials/how-to-use-cron-to-automate-tasks-ubuntu-1804). You can then edit your ~/.bashrc file and add the lines:

```bash
alias backup_wow="docker run -it --rm \
    -v /some/folder/wow_backup/.ssh:/.ssh \
    -v /some/folder/wow_backup/backups:/backups \
    --network=really_awesome_docker_network db_backup:1.0 \
    --ip_host db \
    --db_user trinity \
    --password trinity \
    --databases 'auth world characters' \
    --port_remote 22 \
    --user_remote trinity \
    --dir_remote backups \
    --ip_remote strangeforeignland.ddns.net \
    --credential_file id_rsa"
```

## Levers and Dials

There are a fair number of ways to run this thing but it boils down to three major ways.

1. Build this container with environment variables set to your preference.
2. Build this container with some environment variables set and pass the remainder in as CLI parameters.
3. Pass everything in as CLI parameters at run time.

Please keep in mind that caching passwords in Docker containers is probably just **not a good idea**(TM).

All of the variables below may be set via environment variables by including them as upper case versions, e.g. CREDENTIAL_FILE = some/silly/path, in the Dockerfile, or they may be called at runtime with something like `docker run db_backup:1.0 --credential_file "some/silly/path"`. Either way will work and passing things like **passwords** in via CLI is possibly more secure, depending on your environment.

### DLY_BACKUP_COUNT

* Help String: The number of concurrent daily backups to retain.
* Default Value: 5

### WLY_BACKUP_COUNT

* Help String: The number of concurrent weekly backups to retain.
* Default Value: 5

### MLY_BACKUP_COUNT

* Help String: The number of concurrent monthly backups to retain.
* Default Value: 5

### IP_HOST

* Help String: The IP address (or any string that fits the mysqldump -h parameter) of the database to dump.
* Default Value: None
* Possible Values: '127.0.0.1', or '192.168.1.191', or even a hostname if you're savvy, e.g. 'db'.

### DB_USER

* Help String: The MySQL user you wish to run the backup as.
* Default Value: root

### PASSWORD

* Help String: The password for the MySQL user. You should be using the CLI, and not environment variables, for this.
* Default Value: None

### DATABASES

* Help String: Space separated list of databases you wish to back up.
* Default Value: 'all'
* Possible Values: 'all' works as a keyword, but otherwise pass specific database names. For me that means if I want to back up the world, character, and auth databases I need to pass 'world character auth'.

### SKIP_LOCAL

* Help String: A boolean that can be used to skip a local dump.
* Default Value: False

### DIR_LOCAL

* Help String: A local directory to create a copy into.
* Default Value: '/backups'

This will be dumping to the Docker containers /backups directory. If you wish those to *persist* then you need to mount a volume to /backups.

### SKIP_REMOTE

* Help String: A boolean that can be used to skip a remote dump.
* Default Value: False

### IP_REMOTE

* Help String: The IP address of the remote host to store a backup on.
* Default Value: None
* Possible Values: Any resolvable hostname / IP address, similar to above with IP_HOST.

### USER_REMOTE

* Help String: The username to use to attempt connection with the remote host.
* Default Value: None

### PASS_REMOTE

* Help String: The password to use to attempt connection with the remote host.
* Default Value: None

### PORT_REMOTE

* Help String: The TCP SSH port of the remote host to store a backup on.
* Default Value: 22

### DIR_REMOTE

* Help String: A remote directory to create a copy into.
* Default Value: None

### CREDENTIAL_FILE

* Help String: The name of the public key you wish to use. Note that it must be mounted into /.ssh.
* Default Value: None

## Possible Command

In the command below I am cloning down this repository, then building and running the database backup utility.

I am mounting the credential file associated with this routine from its location in the docker appdata folder, into .ssh.

I am also mounting the local directory where I want to store backups into /backups.

I connect it to the network that my database is running on. Since the network is built in a Docker Compose file and the database is hostnamed to db, I can simply use 'db' in the --ip_host argument.

```
git clone https://github.com/LunarEngineer/db_backup.git && \

cd db_backup && \

docker build . -t db_backup:1.0 && \

docker run -it --rm \
    -v /docker/appdata/db_backup/.ssh:/.ssh \
    -v /docker/appdata/db_backup/backups:/backups \
    --network=database-docker_default db_backup:1.0 \
    --ip_host db \
    --db_user steve \
    --password steves_password \
    --databases 'list of databases' \
    --port_remote 22 \
    --user_remote curious_consumer \
    --dir_remote backups \
    --ip_remote strangeforeignland.ddns.net \
    --credential_file id_rsa

```

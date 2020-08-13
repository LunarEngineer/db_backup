####################################################################
# The purpose of this code is to perform scheduled backups of a
#   database to a local and / or remote server.
####################################################################

# pylint: disable=no-member
import argparse
import os
import paramiko
import subprocess
import time

from datetime import date

####################################################################
# Establish some default properties in a single location. This
#   makes maintenance and flexibility a bit better. This dictionary
#   is used to construct the class properties on instantiation, the
#   command line argument parameters, and sets defaults. Adding and
#   modifying command line parameters is as simple as changing them
#   here.
####################################################################

__DEFAULT_PROPERTIES__ = {
    'DLY_BACKUP_COUNT': {
        'help': 'The number of concurrent daily backups to retain.',
        'default': 5
    },
    'WLY_BACKUP_COUNT': {
        'help': 'The number of concurrent weekly backups to retain.',
        'default': 5
    },
    'MLY_BACKUP_COUNT': {
        'help': 'The number of concurrent monthly backups to retain.',
        'default': 5
    },
    'IP_HOST': {
        'help': 'The IP address (or any string that fits the mysqldump -h parameter) of the database to dump.',
        'default': None
    },
    'DB_USER': {
        'help': 'The MySQL user you wish to run the backup as.',
        'default': 'root'
    },
    'PASSWORD': {
        'help': 'The password for the MySQL user. You should be using the CLI, and not environment variables, for this.',
        'default': None
    },
    'DATABASES': {
        'help': 'Space separated list of databases you wish to back up.',
        'default': 'all',
        'nargs': '?'
    },
    'DIR_LOCAL': {
        'help': 'A local directory to create a copy into.',
        'default': '/backups'
    },
    'SKIP_REMOTE': {
        'help': 'A boolean that can be used to skip a remote dump.',
        'default': False
    },
    'IP_REMOTE': {
        'help': 'The IP address of the remote host to store a backup on.',
        'default': None
    },
    'USER_REMOTE': {
        'help': 'The username to use to attempt connection with the remote host.',
        'default': None
    },
    'PASS_REMOTE': {
        'help': 'The password to use to attempt connection with the remote host.',
        'default': None
    },
    'PORT_REMOTE': {
        'help': 'The TCP SSH port of the remote host to store a backup on.',
        'default': 22
    },
    'DIR_REMOTE': {
        'help': 'A remote directory to create a copy into.',
        'default': None
    },
    'CREDENTIAL_FILE':{
        'help': 'The name of the public key you wish to use. Note that it must be mounted into /.ssh.',
        'default': None
    }
}

####################################################################
# Build the CLI parser from the defaults dictionary above. Note that
#   the arguments are being 'tuple-unpacked' and so you can make
#   them as arbitrarily complex as you'd like. Simple add dictionary
#   keys above!
####################################################################
parser = argparse.ArgumentParser(
    prog='db_backup',
    description='Remote Database Backup Utility'
    )

for param in __DEFAULT_PROPERTIES__:
    arg_val = __DEFAULT_PROPERTIES__[param]
    parser.add_argument(f'--{param.lower()}', **arg_val)


class db_bkp():
    """ Class to automate backups """

    def __init__(self,args):
        # Go get all the arguments.
        self._scrape_args(args)
        # Then do a little bit of cleaning.
        self._bookkeeping()


    def _scrape_args(self,args):
        """ Pulls command line arguments and environmental variables

        This is a helper function that will get the 'right' value
        for a CLI argument. It does that by *prioritizing* command
        line arguments over environment variables over defaults.

        That means that if you don't change anything, you get
        defaults. If you change an environment variable it will take
        precedence. If you change a command line parameter, it will
        take precedence over *that*.

        Parameters
        ----------
        args: environment
            Args is an environment created by the argparse utility
        """
        def checkcli(args,v):
            # Helper function to get a cli arg from argparse if
            #   it exists, and none otherwise.
            try:
                return getattr(args,v)
            except:
                return None

        for k, v in __DEFAULT_PROPERTIES__.items():
            # 1. Get the default value of the property
            value = v['default']
            # 2. Was there a passed environment variable?
            if os.getenv(k) is not None: value = os.getenv(k)
            # 3. Was there a passed CLI argument?
            if checkcli(args,k.lower()) is not None: value = checkcli(args,k.lower())
            setattr(self, f'_{k.lower()}', value)


    def _bookkeeping(self):
        # Consolidate the number of copies and ensure they are int
        self._backup_counts = {
            'DLY_BACKUP_COUNT': int(float(self._dly_backup_count)),
            'WLY_BACKUP_COUNT': int(float(self._wly_backup_count)),
            'MLY_BACKUP_COUNT': int(float(self._mly_backup_count))
        }
        # Get today's date
        today = date.today()
        # Are we making a weekly?
        self._make_weekly = today.weekday()==6
        # What about a monthly?
        self._make_monthly = today.strftime("%d")=="01"
        # Split apart the list of databases
        databases = self._databases.split(" ")
        # Sort them
        databases.sort()
        # Then join them back together to make a filename.
        self._filename = f"{'-'.join(databases)}_{today.strftime('%Y-%m-%d')}.sql"
        init_str = f"""
        ############################
        Database Backup Utility:
        Parameters:
        \tDatabase Host:                {self._ip_host}
        \tDatabase User:                {self._db_user}
        \tDatabase Password Passed:     {self._password is not None}
        \tDatabases:                    {self._databases}
        \tDump File Name:               *_{self._filename}
        \tLocal Directory:              {self._dir_local}
        \tSkip Remote:                  {self._skip_remote}
        \tRemote Host:                  {self._ip_remote}
        \tRemote Port:                  {self._port_remote}
        \tRemote Username:              {self._user_remote}
        \tRemote Directory:             {self._dir_remote}
        \tCredential File:              {self._credential_file}
        \tDaily Backups to Maintain:    {self._backup_counts['DLY_BACKUP_COUNT']}
        \tWeekly Backups to Maintain:   {self._backup_counts['WLY_BACKUP_COUNT']}
        \tMonthly Backups to Maintain:  {self._backup_counts['MLY_BACKUP_COUNT']}
        \tCreating Weekly Backup:       {self._make_weekly}
        \tCreating Monthly Backup:      {self._make_monthly}
        """
        print(init_str)


    def _create_dump_cmd(self):
        """ Iteratively build a mysqldump command
        
        This uses passed command line arguments and environment
        variables to construct a mysqldump command.
        Includes host, user, password, and databases capability.
        """
        # Start with a simple command
        dump_cmd = "mysqldump"
        # Add the database IP address if existent
        if self._ip_host is not None:
            dump_cmd += f" -h'{self._ip_host}'"
        # Add the user
        dump_cmd += f" -u'{self._db_user}'"
        # Add the password if there is one
        if self._password is not None:
            dump_cmd += f" -p'{self._password}'"
        # Is there a list of databases?
        if self._databases == 'all':
            dump_cmd += f" --all-databases"
        else:
            dump_cmd += f" --databases {self._databases}"
        return dump_cmd


    def read_db(self,debug=False):
        """ Helper function to read a mysqldump into a stream.

        Parameters
        ----------
        debug: bool = False
            Prints the command generated to call mysqldump.
            Be warned that this includes the password and therefore
            this should *never* be turned on in production.
        """
        dump_cmd = self._create_dump_cmd()
        if debug: print(dump_cmd)
        # I would rather not run with shell
        # TODO: Look into fixing this to just use run without a shell.
        # The error it was throwing was when it was trying to put
        # --databases into the run command.
        process = subprocess.Popen(dump_cmd, 
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           shell = True,
                           universal_newlines=True)
        print("Running mysqldump")
        self.stdout, self.stderr = process.communicate()
        if self.stderr is not None and len(self.stderr):
            raise RuntimeError(f"Unable to properly connect to the database with standard error {self.stderr}")


    def dump_local(self,debug:bool=False):
        """ Curates local files, deleting the old ones.

        Parameters
        ----------
        debug: bool = False
            This will print status messages to STDOUT and will print
            information including which daily, weekly, and monthly
            backups exist and which will get pruned.
        """
        if not self._skip_local:
            # Where am I dumping this?
            # TODO: Instead of writing to three separate files
            #   create one and copy it.
            # 1. Do the daily
            f_daily = os.path.join(self._dir_local,f"DAILY_{self._filename}")
            if debug: print(f"\tWriting local file: {f_daily}")
            with open(f_daily,'w') as f:
                f.writelines(self.stdout)
            # 2. Do the weekly
            if self._make_weekly:
                f_weekly = os.path.join(self._dir_local,f"WEEKLY_{self._filename}")
                if debug: print(f"\tWriting local file: {f_weekly}")
                with open(f_weekly,'w') as f:
                    f.writelines(self.stdout)
            # 3. Do the monthly
            if self._make_monthly:
                f_monthly = os.path.join(self._dir_local,f"MONTHLY_{self._filename}")
                if debug: print(f"\tWriting local file: {f_monthly}")
                with open(f_monthly,'w') as f:
                    f.writelines(self.stdout)
            # Dig into the local filestructure and clean it up
            self.manage_files(os.listdir(self._dir_local))
            # Finally clean up anything in the drop list.
            while self._drop_list:
                fl = self._drop_list.pop()
                fl = os.path.join(self._dir_local,fl)
                if debug: print(f"\t\tRemoving {fl}")
                os.remove(fl)
            if debug:
                self.manage_files(os.listdir(self._dir_local),debug)


    def dump_remote(self,debug:bool=False):
        """ Curates remote files, deleting the old ones.

        Parameters
        ----------
        debug: bool = False
            This will print status messages to STDOUT and will print
            information including which daily, weekly, and monthly
            backups exist and which will get pruned.
        """
        if not self._skip_remote:
            print("Working on remote")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
            if self._credential_file is not None:
                client.connect(
                    self._ip_remote,
                    port         = self._port_remote,
                    username     = self._user_remote,
                    # Could add a passphrase here, but I really want this to fire automatically.
                    key_filename = f'.ssh/{self._credential_file}'
                )
            else:
                client.connect(
                    self._ip_remote,
                    port         = self._port_remote,
                    username     = self._user_remote,
                    password     = self._pass_remote
                )
            # Open a secure file transfer protocol channel object
            sftp = client.open_sftp()
            # Get the local file
            # 1. Do the daily
            f_daily_l = os.path.join(self._dir_local,f"DAILY_{self._filename}")
            f_daily_r = os.path.join(self._dir_remote,f"DAILY_{self._filename}")
            if debug: print(f"\tWriting remote file: {f_daily_r}")
            try:
                sftp.put(f_daily_l, f_daily_r)
            except:
                raise Exception("Unable to copy daily backup.")
            # 2. Do the weekly
            f_weekly_l = os.path.join(self._dir_local,f"WEEKLY_{self._filename}")
            f_weekly_r = os.path.join(self._dir_remote,f"WEEKLY_{self._filename}")
            if debug: print(f"\tWriting remote file: {f_weekly_r}")
            try:
                sftp.put(f_weekly_l, f_weekly_r)
            except:
                raise Exception("Unable to copy weekly backup.")
            # 3. Do the monthly
            f_monthly_l = os.path.join(self._dir_local,f"MONTHLY_{self._filename}")
            f_monthly_r = os.path.join(self._dir_remote,f"MONTHLY_{self._filename}")
            if debug: print(f"\tWriting remote file: {f_monthly_r}")
            try:
                sftp.put(f_monthly_l, f_monthly_r)
            except:
                raise Exception("Unable to copy monthly backup.")
            # Dig into the remote filestructure and clean it up
            self.manage_files(sftp.listdir(self._dir_remote))
            # Finally clean up anything in the drop list.
            while self._drop_list:
                fl = self._drop_list.pop()
                fl = os.path.join(self._dir_remote,fl)
                if debug: print(f"\t\tRemoving {fl}")
                sftp.remove(fl)
            if debug:
                self.manage_files(sftp.listdir(self._dir_remote),debug)
            # Clean up, clean up, everybody everywhere!
            sftp.close()
            client.close()


    def manage_files(self,file_list,debug:bool=False):
        """ Manage a list of file names

        This function walks through a list of files and curates them.
        It looks for unique combinations of X_Y_Z where X is in the
        set {DAILY, WEEKLY, MONTHLY}, Y is a set of '-' separated
        table names, and Z is a 'YYYY-MM-DD' formatted date string.

        Each unique combination of Y retains the top `n` combinations
        of X_Y_Z for each valid level of X. That means that it's
        allowed to keep `n` values of DAILY_Y_Z, `n` WEEKLY, and `n`
        MONTHLY.

        Parameters
        ----------
        file_list: list[str]
            A list of string filenames of pattern X_Y_Z
        """
        # Rip apart the file list.
        X, Y, Z = zip(*[_.split('_') for _ in file_list])
        # Make an empty drop list.
        self._drop_list = []
        def prune(backup_list, n:int=5):
            while len(backup_list) > n:
                self._drop_list.append(backup_list.pop(0))
        # For every unique backup *set* (i.e. DAILY)
        if debug: print(f"######## Unique Y: {set(Y)}")
        for y in set(Y):
            # TODO: Add a test file for auth_character
            file_list = ['_'.join([x1,x2,x3]) for x1,x2,x3 in zip(X,Y,Z) if x2 == y]
            # Split the list into daily / weekly / monthly
            daily_backups = [_ for _ in file_list if "DAILY" in _]
            weekly_backups = [_ for _ in file_list if "WEEKLY" in _]
            monthly_backups = [_ for _ in file_list if "MONTHLY" in _]
            # Sort them from old to new
            daily_backups.sort()
            weekly_backups.sort()
            monthly_backups.sort()
            # Prune the lists as necessary
            prune(daily_backups, self._backup_counts['DLY_BACKUP_COUNT'])
            prune(weekly_backups, self._backup_counts['WLY_BACKUP_COUNT'])
            prune(monthly_backups, self._backup_counts['MLY_BACKUP_COUNT'])

            if debug:
                str_d = '\n\t\t\t'.join([f'{i+1}: {_}' for i, _ in enumerate(daily_backups)])
                str_w = '\n\t\t\t'.join([f'{i+1}: {_}' for i, _ in enumerate(weekly_backups)])
                str_m = '\n\t\t\t'.join([f'{i+1}: {_}' for i, _ in enumerate(monthly_backups)])
                str_p = '\n\t\t\t'.join([f'{i+1}: {_}' for i, _ in enumerate(self._drop_list)])

                debug_str = f"""
                Backups: {y}
                Daily:\n\t\t\t{str_d}
                Weekly:\n\t\t\t{str_w}
                Monthly:\n\t\t\t{str_m}
                To Prune:\n\t\t\t{str_p}
                """
                print(debug_str)


def main(args):
    # Create a backup object
    bu = db_bkp(args)
    # Read the data
    bu.read_db()
    # Then dump it locally
    bu.dump_local()
    # aaaand remotely.
    bu.dump_remote()
    print("Backups Complete")


if __name__=='__main__':
    args = parser.parse_args()
    main(args)

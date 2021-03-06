import argh, os, pwd, sys
from gitdh.gitdh import gitDhMain
from gitdh.config import Config

try:
	from shlex import quote
except ImportError:
	import re
	_find_unsafe = re.compile(r'[^\w@%+=:,./-]', re.ASCII).search
	def quote(s):
		"""Return a shell-escaped version of the string *s*."""
		if not s:
			return "''"
		if _find_unsafe(s) is None:
			return s

		# use single quotes, and put single quotes into double quotes
		# the string $'b is then quoted as '$'"'"'b'
		return "'" + s.replace("'", "'\"'\"'") + "'"


postreceiveContent = """#!/bin/sh

configFile='{0}'
{1}
while read oldrev newrev refname
do
	git-dh postreceive $configFile $oldrev $newrev $refname
done

exit 0
"""

cronContent = """# {0}: Cron Job file for git-dh

PATH={1}
MAILTO={2}

{3}    {4}    {5}
"""


@argh.arg('target', nargs="+", help="A configuration file or a repository for which to perform cron job operations")
def cron(*target):
	"Process cron job operations"
	if len(target) == 0:
		print("Please provide at least one target, for more info call with -h", file=sys.stderr)
		sys.exit(1)
	for t in target:
		gitDhMain(t, 'cron', [])

@argh.arg('target', help="The configuration file for which to process post-receive information")
@argh.arg('oldrev', help="The oldrev as passed in by git")
@argh.arg('newrev', help="The newrev as passed in by git")
@argh.arg('refname', help="The refname as passed in by git")
def postreceive(target, oldrev, newrev, refname):
	"Process postreceive operations"
	try:
		del os.environ['GIT_DIR']
	except KeyError:
		pass
	gitDhMain(target, 'postreceive', (oldrev, newrev, refname))

@argh.named('postreceive')
@argh.arg('target', nargs="+", help="A configuration file or a repository for which post-receive hooks are to be created")
@argh.arg('--printOnly', '--print', '-p', help="Only print the files' content")
@argh.arg('--force', '-f', help="Overwrite existing files")
@argh.arg('--quiet', '-q', help="Only print errors, no status information")
@argh.arg('--mode', '-m', help="The mode of the created files (file permissions / bits)")
def installPostreceive(printOnly=False, force=False, quiet=False, mode='755', *target):
	"Install post-receive hooks"
	if force and printOnly:
		print("Invalid options: --printOnly and --force both set", file=sys.stderr)
		sys.exit(1)
	if len(target) == 0:
		print("Please provide at least one target, for more info call with -h", file=sys.stderr)
		sys.exit(1)

	filesToWrite = {}
	virtEnvStr = ''
	if 'VIRTUAL_ENV' in os.environ:
		virtEnvStr = '. %s/bin/activate\n' % (quote(os.environ['VIRTUAL_ENV']),)
	for t in target:
		try:
			c = Config.fromFilePath(t)
			if c.repoPath is None:
				raise Exception("Missing RepositoryPath for '%s'" % (t))
			fPath = os.path.join(c.repoPath, 'hooks/post-receive')
			if not printOnly and not os.access(os.path.dirname(fPath), os.W_OK):
				raise Exception("Can't write to '%s'" % (fPath,))
			if not printOnly and os.path.exists(fPath) and not force:
				raise Exception("'%s' exists already, use --force to overwrite" % (fPath,))

			configFile = os.path.abspath(t)
			filesToWrite[fPath] = postreceiveContent.format(configFile, virtEnvStr)
		except Exception as e:
			print(e, file=sys.stderr)
			sys.exit(1)

	for (path, content) in filesToWrite.items():
		if printOnly:
			yield "# File '%s'" % path
			yield content
		else:
			try:
				if not quiet:
					yield "Writing post-receive hook '%s'" % (path,)
				with open(path, 'w') as f:
					f.write(content)
					# Only on UNIX
					#os.fchmod(f, mode)
				os.chmod(fPath, int(mode, 8))
			except (IOError, OSError) as e:
				print(e, file=sys.stderr)
				print("Please check '%s'" % (path,), file=sys.stderr)
				sys.exit(1)

@argh.named('cron')
@argh.arg('name', help="Name of the cron job file to be placed in /etc/cron.d")
@argh.arg('target', nargs="+", help="A configuration file or a repository to be included in the cron job")
@argh.arg('--user', '-u', help="The user to execute gitdh under in the cron job; If none it defaults to the current user")
@argh.arg('--printOnly', '--print', '-p', help="Only print the file content")
@argh.arg('--force', '-f', help="Overwrite an existing file")
@argh.arg('--quiet', '-q', help="Only print errors, no status information")
@argh.arg('--mailto', help="The MAILTO to be written to the cron job file")
@argh.arg('--unixPath', '--path', help="The PATH to be written to the cron job file; If None it defaults to the current PATH")
@argh.arg('--interval', '-i', help="The interval with which the cron job is to be executed")
@argh.arg('--mode', '-m', help="The mode of the created cron job file (file permissions / bits)")
def installCron(name, user=None, printOnly=False, force=False, quiet=False,
				mailto='root', unixPath=None, interval='*/5 * * * *', mode='644', *target):
	"Install a cron job in /etc/conf.d"
	if force and printOnly:
		print("Invalid options: --printOnly and --force both set", file=sys.stderr)
		sys.exit(1)
	if len(target) == 0:
		print("Please provide at least one target, for more info call with -h", file=sys.stderr)
		sys.exit(1)

	if user is None:
		user = pwd.getpwuid(os.getuid())[0]

	fPath = os.path.join('/etc/cron.d', name)
	try:
		for t in target:
			Config.fromPath(t)
		if not printOnly and not os.access(os.path.dirname(fPath), os.W_OK):
			raise Exception("Can't write to '%s'" % (fPath,))
		if not printOnly and os.path.exists(fPath) and not force:
			raise Exception("'%s' already exists, use --force to overwrite" % (fPath,))
	except Exception as e:
		print(e, file=sys.stderr)
		sys.exit(1)

	cmdStr = 'git-dh cron'
	for t in target:
		cmdStr += ' ' + quote(os.path.abspath(t))
	if 'VIRTUAL_ENV' in os.environ:
		virtEnvPath = os.path.join(os.environ['VIRTUAL_ENV'], 'bin', 'activate')
		cmdStr = ". %s; %s" % (quote(virtEnvPath), cmdStr)
		cmdStr = "bash -c %s" % (quote(cmdStr),)
	if unixPath is None:
		unixPath = os.environ.get('PATH', '')
	content = cronContent.format(fPath, unixPath, mailto, interval, user, cmdStr)

	if printOnly:
		yield "# File '%s'" % fPath
		yield content
	else:
		try:
			if not quiet:
				yield "Writing cron job '%s'" % (fPath,)
			with open(fPath, 'w') as f:
				f.write(content)
				# Only on UNIX
				#os.fchmod(f, mode)
			os.chmod(fPath, int(mode, 8))
		except (IOError, OSError) as e:
			print(e, file=sys.stderr)
			print("Please check '%s'" % (fPath,), file=sys.stderr)
			sys.exit(1)


parser = argh.ArghParser(description="Tool to automatically deploy git commits using post-receive hooks and cron jobs")
parser.add_commands([cron, postreceive])
parser.add_commands([installPostreceive, installCron], help="Commands installing files to automatically perform operations", namespace="install")

def main():
	parser.dispatch()

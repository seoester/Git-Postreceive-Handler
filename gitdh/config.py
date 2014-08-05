# -*- coding: utf-8 -*-

from gitdh import git
from collections import Mapping
from configparser import ConfigParser
import os.path

class Config(ConfigParser):

	@staticmethod
	def fromPath(path):
		if os.path.isfile(path):
			return Config.fromFilePath(path)
		elif os.path.isdir(path):
			config = Config.fromGitRepo(path)
			if not 'Git' in config:
				config['Git'] = { 'RepositoryPath': path }
			return config
		else:
			raise Exception("Can't read config from '%s'" % (path,))

	@staticmethod
	def fromGitRepo(repoPath):
		gC = git.Git(repoPath)

		if not "gitdh" in gC.getBranches():
			raise Exception("No Branch 'gitdh' in repository '%s'" % (repoPath,))

		gFile = None
		for file in gC.getFiles(branch="gitdh"):
			if file.getFileName() == "gitdh.conf":
				gFile = file
				break
		if gFile == None:
			raise Exception("No File 'gitdh.conf")

		config = Config()
		config.read_string(gFile.getFileContent())
		return config

	@staticmethod
	def fromFilePath(filePath):
		with open(filePath) as f:
			config = Config.fromFile(f)

		return config

	@staticmethod
	def fromFile(fileObj):
		c = Config()
		c.read_file(fileObj)
		return c

	def __init__(self):
		super().__init__()
		self.branches = ConfigBranches(self)


class ConfigBranches(Mapping):
	def __init__(self, cfgParser):
		self._cfgParser = cfgParser

	def keys(self):
		for section in self._cfgParser:
			if not self._isBranchSection(section):
				continue
			yield section

	def __len__(self):
		return len([i for i in self.keys()])

	def __contains__(self, item):
		return item in self.keys()

	def __iter__(self):
		return self.keys()

	def __getitem__(self, key):
		if not self._isBranchSection(key):
			raise KeyError("Invalid branch section '%s'" % (key,))
		return self._cfgParser[key]

	def _isBranchSection(self, key):
		return not key in ('Git', 'DEFAULT', 'Database') and not ("-" in key and key[key.rfind('-') + 1:] == "command")
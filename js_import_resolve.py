import sublime
import sublime_plugin
import fnmatch
import json
import os
import re

#
# Utils
#

def extract_import_values(line):
  commonjs = re.finditer(r'\brequire\s*\(["\']([^"\']+)', line)
  commonjs_values = []
  for group in commonjs:
    commonjs_values.append(group.group(1))
  if len(commonjs_values) > 0:
    return commonjs_values
  es6import = re.search(r'import.*\sfrom\s+["\']([^"\']+)', line)
  if es6import:
    return [es6import.group(1)]
  return []

assert extract_import_values("const { createCanvas } = require('canvas');") == ['canvas']
assert extract_import_values("const { createCanvas } = require ('canvas');") == ['canvas']
assert extract_import_values("const { createCanvas } = require(\"canvas\");") == ['canvas']
assert extract_import_values("const { createCanvas } = require('asd-foo');") == ['asd-foo']
assert extract_import_values("const { createCanvas } = require('./asd.js');") == ['./asd.js']
assert extract_import_values("const { createCanvas } = require('../asd.js');") == ['../asd.js']
assert extract_import_values("const { createCanvas } = require('./nested/asd.js');") == ['./nested/asd.js']

assert extract_import_values("const foo = require('asd'); const yay = require('hmm');") == ['asd', 'hmm']

assert extract_import_values("import { createCanvas } from 'canvas';") == ['canvas']
assert extract_import_values("import { createCanvas } from 'canvas';") == ['canvas']
assert extract_import_values("import { createCanvas } from \"canvas\";") == ['canvas']
assert extract_import_values("import { createCanvas } from 'asd-foo';") == ['asd-foo']
assert extract_import_values("import { createCanvas } from './asd.js';") == ['./asd.js']
assert extract_import_values("import { createCanvas } from '../asd.js';") == ['../asd.js']
assert extract_import_values("import { createCanvas } from './nested/asd.js';") == ['./nested/asd.js']

def clean_path(path):
  path = re.sub(r'\/\.\/', '/', path)
  path = re.sub(r'\/[^\/]+\/\.\.\/', '/', path)
  return path

assert clean_path('/foo/./bar') == '/foo/bar'
assert clean_path('/foo/../bar') == '/bar'

def resolve_relative_path(path1, path2):
  longest_common = 0
  segments1 = list(filter(lambda string: string != '', re.split(r'/', path1)))
  segments2 = list(filter(lambda string: string != '', re.split(r'/', path2)))
  longest_common = 0
  for index, segment in enumerate(segments1):
    if segments2[index] != segment:
      break
    longest_common += 1
  segments1 = segments1[longest_common:]
  segments2 = segments2[longest_common:]
  if len(segments1) == 0:
    return './' + '/'.join(segments2)
  else:
    parents = ['..'] * len(segments1)
    return '/'.join(parents) + '/' + '/'.join(segments2)

assert resolve_relative_path('/foobar/test', '/foobar/test/asd.js') == './asd.js'
assert resolve_relative_path('/foobar/test', '/foobar/src/asd.js') == '../src/asd.js'
assert resolve_relative_path('/', '/foobar/test.js') == './foobar/test.js'
assert resolve_relative_path('/foo', '/foo/foobar/test.js') == './foobar/test.js'

def resolve_js_file_path(path):
  variations = [path]
  if not path.endswith('.js'):
    variations.append(path + '.js')
  if not path.endswith('.json'):
    variations.append(path + '.json')
  for variation in variations:
    if os.path.isfile(variation):
      return variation
  return None

def find_package_root(dirname):
  counter = 0
  while dirname != '/' and counter < 20:
    if os.path.isfile(os.path.join(dirname, 'package.json')):
      return dirname
    counter += 1
    dirname = os.path.dirname(dirname)

def should_do_autocomplete(line_until_cursor):
  if re.match(r'.*\brequire\s*\([\'"]\w', line_until_cursor):
    return True
  if re.match(r'.*\bfrom\s* [\'"]\w', line_until_cursor):
    return True
  return False

assert should_do_autocomplete('') == False
assert should_do_autocomplete('foo') == False
assert should_do_autocomplete('require') == False
assert should_do_autocomplete('from') == False
assert should_do_autocomplete('var asd = require("a') == True
assert should_do_autocomplete('var asd = require(\'a') == True
assert should_do_autocomplete('import asd from "a') == True
assert should_do_autocomplete('import asd from \'a') == True

#
# Main
#

class JsImportResolveListener(sublime_plugin.EventListener):
  def on_hover(self, view, point, hover_zone):
    line = view.substr(view.line(point))
    values = extract_import_values(line)
    if len(values) > 0:
      paths = []
      for value in values:
        if value[0] == '.':
          file_path = resolve_js_file_path(clean_path(os.path.join(os.path.dirname(view.file_name()), value)))
          if file_path:
            paths.append(file_path)
            break
        else:
          dirname = os.path.dirname(view.file_name())
          package_root = find_package_root(dirname)
          module_path = os.path.join(package_root, 'node_modules', value)
          if os.path.isdir(module_path):
            with open(os.path.join(module_path, 'package.json'), 'r') as file:
              package_information = json.loads(file.read())
              if package_information['main']:
                file_path = resolve_js_file_path(clean_path(os.path.join(module_path, package_information['main'])))
                paths.append(file_path)
      html = '<br>'.join(map(lambda path: '<a href="' + path + '">' + path + '</a>', paths))
      view.show_popup(html, sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 1000, 1000, lambda href: view.window().open_file(href))

  def on_query_completions(self, view, prefix, locations):
    location = locations[0]
    line_until_cursor = view.substr(sublime.Region(view.line(location).begin(), location))
    if should_do_autocomplete(line_until_cursor):
      files = []
      dirname = os.path.dirname(view.file_name())
      package_root = find_package_root(dirname)
      # read package.json for dependencies
      with open(os.path.join(package_root, 'package.json'), 'r') as file:
        package_information = json.loads(file.read())
        if 'dependencies' in package_information:
          for dependency_name in package_information['dependencies']:
            if dependency_name.startswith(prefix):
              files.append((dependency_name + '\t' + 'package.json', dependency_name))
        if 'devDependencies' in package_information:
          for dependency_name in package_information['devDependencies']:
            if dependency_name.startswith(prefix):
              files.append((dependency_name + '\t' + 'package.json', dependency_name))
      # find project JS-files recursively https://stackoverflow.com/a/2186565/239527
      for root, dirnames, filenames in os.walk(package_root):
        for filename in fnmatch.filter(filenames, prefix + '*.js'):
          if '/node_modules/' not in root:
            absolute_path = os.path.join(root, filename)
            relative_path = resolve_relative_path(dirname, absolute_path)
            files.append((filename + '\t' + relative_path, relative_path))
      return files

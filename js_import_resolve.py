import sublime
import sublime_plugin
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

#
# Main
#

class HoverListener(sublime_plugin.EventListener):
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
          counter = 0
          while dirname != '/' and counter < 20:
            if os.path.isdir(os.path.join(dirname, 'node_modules')):
              module_path = os.path.join(dirname, 'node_modules', value)
              if os.path.isdir(module_path):
                with open(os.path.join(module_path, 'package.json'), 'r') as file:
                  package_information = json.loads(file.read())
                  if package_information['main']:
                    file_path = resolve_js_file_path(clean_path(os.path.join(module_path, package_information['main'])))
                    paths.append(file_path)
              break
            counter += 1
            dirname = os.path.dirname(dirname)
      html = '<br>'.join(map(lambda path: '<a href="' + path + '">' + path + '</a>', paths))
      view.show_popup(html, sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 1000, 1000, lambda href: view.window().open_file(href))

import re
import os
import argparse
import json
import pdfkit


def create_file_documentation_dict (filename):
    with open(filename, 'r') as file_data:
        file_lines = [line.strip() for line in file_data.readlines()]
    
    docs = {'functions': [], 'variables': []}

    for line_num in range(len(file_lines)):
        line = file_lines[line_num]
        if line.startswith('/**'):
            if is_variable(file_lines, line_num):
                docs['variables'].append(add_doc(file_lines, line_num, is_variable=True))
            else:
                docs['functions'].append(add_doc(file_lines, line_num, is_variable=False))
    return docs


def is_variable (file_lines, line_num):
    while True:
        if '@var' in file_lines[line_num]:
            return True
        elif '*/' in file_lines[line_num]:
            return False
        line_num += 1


def add_doc (file_lines, line_num, is_variable):
    line = file_lines[line_num]
    if '*/' in line:
        if is_variable:
            return add_oneline_variable(file_lines, line_num)
        else:
            return add_oneline_function(file_lines, line_num)
    else:
        if is_variable:
            return add_multiline_variable(file_lines, line_num)
        else:
            return add_multiline_function(file_lines, line_num)


def add_oneline_function(file_lines, line_num):
    description_line = file_lines[line_num]
    next_line = file_lines[line_num + 1]
    function_doc = {'description': [], 'parameters': [], 'returns': None, 'name': '', 'async': False, 'helper': False, 'is_variable': False}
    function_doc['description'] = [description_line[3:-2].strip()]
    function_doc['name'] = extract_function_name(next_line)
    return function_doc


def add_oneline_variable (file_lines, line_num):
    # /** @var {Type} vName - description is here */
    description_line = file_lines[line_num][3 : -2].strip()  # get rid of /** and */
    next_line = file_lines[line_num + 1]
    variable_doc = {'name': '', 'type': '', 'description': []}
    description_line_split = [x.strip() for x in description_line.split(' ')]

    variable_doc['type'] = description_line_split[1][1:-1].strip()
    variable_doc['name'] = description_line_split[2]
    variable_doc['description'] = [description_line[description_line.index('-')+1 : ].strip()]
    return variable_doc


def add_multiline_function(file_lines, line_num):
    function_doc = {'description': [], 'parameters': [], 'returns': None, 'name': '', 'async': False, 'helper': False, 'is_variable': False}
    line_counter = line_num+1
    line_of_end_comment = None

    while not line_of_end_comment:
        line = file_lines[line_counter]

        if '*/' in line:
            line_of_end_comment = line_counter
            break

        line = line[2:]
        
        if line.startswith('@param'):
            first_curly_index = line.index('{')
            last_curly_index = line.index('}')
            param_type = line.split(' ')[1].strip()[1:-1]
            param_name = line.split(' ')[2]
            param_description = line[line.index(' - ')+3 : ]
            function_doc['parameters'].append({'type': param_type, 'name': param_name, 'description': param_description})

        elif line.startswith('@returns'):
            return_type = line.split(' ')[1][1:-1].replace('<','&lt;').replace('>','&gt;')
            if len(line.split(' ')) > 2:
                # There is a description, fex @returns {Boolean} isTrue - describe it
                return_description = line[line.index('}')+2 : ]
                function_doc['returns'] = {'type': return_type, 'description': return_description}
        
        elif line.startswith('@helper_function'):
            function_doc['helper'] = True
        
        elif line.startswith('@async'):
            function_doc['async'] = True
        
        else:
            function_doc['description'].append(line)


        line_counter += 1
    
    function_name_line = file_lines[line_of_end_comment + 1]
    parenthesis_index = function_name_line.index('(')

    function_doc['name'] = extract_function_name(function_name_line)
    return function_doc


def add_multiline_variable (file_lines, line_num):
    # /**
    # /* @var {type} vName - Description is here 
    # /* and here as well description
    # */
    variable_doc = {'name': '', 'type': '', 'description': []}
    first_line = file_lines[line_num + 1]
    first_start_squiggle_index = first_line.find('{')
    first_end_squiggle_index = first_line.find('}')
    first_dash_index = first_line.find('-')
    variable_doc['type'] = first_line[first_start_squiggle_index+1 : first_end_squiggle_index].strip()
    variable_doc['name'] = first_line[first_end_squiggle_index+1 : first_dash_index].strip()
    variable_doc['description'].append( first_line[first_dash_index+1 : ] )

    line_counter = line_num + 2
    end_of_line_comment = False
    while not end_of_line_comment:
        line = file_lines[line_counter]
        if '*/' in line:
            end_of_line_comment = True
            break
        line_content = line[2 : ].strip()
        variable_doc['description'].append(line_content)
        line_counter += 1

    return variable_doc


def extract_function_name (fname_line):
    parenthesis_index = fname_line.index('(')

    if fname_line.startswith('async function'):
        # async function fName () {}
        return fname_line[15 : parenthesis_index].strip()
    elif fname_line.startswith('async'):
        # { ..., async fName () {}, ... }
        return fname_line[5 : parenthesis_index].strip()
    elif fname_line.startswith('function'):
        # function fName () {}
        return fname_line[8 : parenthesis_index].strip()
    elif 'function' in fname_line and ':' in fname_line and fname_line.index(':')<fname_line.index('function'):
        # {..., x: function () {}, ... }
        return fname_line[0 : fname_line.index(':')].strip()
    elif 'function' in fname_line and '=' in fname_line:
        # fName = function () {},   fName = async function () {},   fName = () => {}
        return fname_line.split(' ')[0].strip()
    elif re.match('^[a-zA-z]{1,}\s{0,}\(.{0,}\)', fname_line):
        # { ..., fName () {}, ... }
        return fname_line[ : parenthesis_index].strip()


def init_output_file (project_name):
    output_file = open(project_name + '.html', 'w+')
    output_file.write('<html><head><style>')
    output_file.write('''
        body {padding: 5px 70px;}
        p, td, th, table, span, div, h1, h3, h4, h5, h5 {color: #555;}
        p, td, th {font-family: Verdana, Geneva, sans-serif; font-size: 15px;}
        h1, h2, h3, h4, h5 {font-family: Georgia, serif;}
        .small_italic {margin-left: 20px; font-weight: normal; font-style: italic; font-size: 18px;}
        .heading-param {font-weight: normal;}
        table {border-collapse: collapse;}
        td, th {border: 1px solid #bbb; padding: 5px 15px; font-weight: normal;}
        th {background-color: #edf2ed;}
        h1 {font-size: 45px; color: black; margin-bottom: }
        h2 {font-size: 33px; color: #111;}
        h3 {font-size: 25px;}
        h4 {font-size: 22px; margin-bottom: 4px; margin-top: 45px; font-weight: normal; letter-spacing: 0.5;}
        h5 {margin: 10px 0 3px 0; font-weight: normal; font-size: 17px;}
        p {margin: 10px 0;}
				hr {margin-top: 25px;}
        .params-table th {background-color: #e8f7e8;}
        .returns-table th {background-color: #f7e8f5;}
        .variable-table th {background-color: #e8f3f7;}
        .param-name-cell, .type-cell {font-family: monospace; white-space: pre;}
        pre {display: inline;}
    ''')
    output_file.write('</head></style><body>')
    output_file.write('<h1>Documentation for project {}</h1>\n\n'.format(project_name))
    return output_file


def js_documentation_to_file (output_file, documentation_dict):
    if len(documentation_dict['data']['variables']) + len(documentation_dict['data']['functions']) == 0:
        return 0

    output_file.write('<hr/>\n\n<h2>File: {}</h2>\n\n'.format(documentation_dict['name']))
    if len(documentation_dict['data']['variables']) > 0:
        output_file.write('<h3 style="margin-bottom: 5px;">Variables</h3>')
        html_snippet = create_html_for_variables(documentation_dict['data']['variables'])
        output_file.write(html_snippet)
        output_file.write('\n\n')

    if len(documentation_dict['data']['functions']) > 0:
        output_file.write('<h3 style="margin-bottom: -40px;">Functions</h3>')
        for function_doc in documentation_dict['data']['functions']:
            html_snippet = create_html_for_function(function_doc)
            output_file.write(html_snippet)
            output_file.write('\n\n')
    return 1


def create_html_for_function (function_doc):
    html_snippet = '<h4>{} <span class="heading-param">({})</span>'.format(function_doc['name'], ', '.join([param['name'] for param in function_doc['parameters']]))

    if function_doc['async']:
        html_snippet += '<span class="small_italic">async</span>'
    if function_doc['helper']:
        html_snippet += '<span class="small_italic">helper</span>'
    html_snippet += '</h4>\n'

    html_snippet += '<p>{}</p>\n'.format(' '.join(function_doc['description']))

    if len(function_doc['parameters']) > 0:
        html_snippet += '<h5 class="parameters-header">Parameters:</h5>'
        html_snippet += '<table class="params-table"><thead><tr><th>Name</th><th>Type</th><th>Decsription</tr></thead>'
        for param in function_doc['parameters']:
            html_snippet += '''
                            <tr>
                                <td class="param-name-cell">{}</td>
                                <td class="type-cell">{}</td>
                                <td class="description-cell">{}</td>
                            </tr>'''.format(
                                param['name'],
                                param['type'].replace('<','&lt;').replace('>','&gt;'),
                                param['description']
                            )
        html_snippet += '</table>'
    
    if function_doc['returns']:
        html_snippet += '<h5 class="returns-header">Returns:</h5>'
        html_snippet += '<table class="returns-table"><thead><tr><th>Type</th><th>Decsription</tr></thead>'
        html_snippet += '''
                        <tr>
                            <td class="type-cell">{}</td>
                            <td class="description-cell">{}</td>
                        </tr>
                        '''.format(
                            function_doc['returns']['type'].replace('<','&lt;').replace('>','&gt;'),
                            function_doc['returns']['description']
                        )
        html_snippet += '</table>'
    
    return html_snippet


def create_html_for_variables (variable_doc_list):
    html_snippet = '<table class="variable-table"><thead><tr><th>Name</th><th>Type</th><th>Decsription</tr></thead>'
    for variable_doc in variable_doc_list:
        html_snippet += '''
                        <tr>
                            <td class="param-name-cell">{}</td>
                            <td class="type-cell">{}</td>
                            <td class="description-cell">{}</td>
                        </tr>'''.format(
                            variable_doc['name'],
                            variable_doc['type'].replace('<','&lt;').replace('>','&gt;'),
                            ' '.join(variable_doc['description'])
                        )
    html_snippet += '</table>'

    return html_snippet


def create_file_documentation_dict_json (json_filename):
    with open(json_filename) as file_data:
        json_data = json.load(file_data)
    documentation_list = [(key, value) for (key, value) in json_data.items() if '__doc' in key]
    documentation_list = [{'name': key[ : -5], 'type': value['type'], 'description': value['description']} for (key, value) in json_data.items() if '__doc' in key]
    return documentation_list


def json_documentation_to_file (output_file, documentation_dict):
    if len(documentation_dict['data']) == 0:
        return
    html_snippet = '<hr/>\n\n<h2>File: {}</h2>\n\n'.format(documentation_dict['name'])
    html_snippet += '<table class="variable-table"><thead><tr><th>Name</th><th>Type</th><th>Decsription</tr></thead>'
    for documentation_item in documentation_dict['data']:
        html_snippet += '''
                        <tr>
                            <td class="param-name-cell">{}</td>
                            <td class="type-cell">{}</td>
                            <td class="description-cell">{}</td>
                        </tr>'''.format(
                            documentation_item['name'],
                            documentation_item['type'].replace('<','&lt;').replace('>','&gt;'),
                            documentation_item['description']
                        )
    html_snippet += '</table>'
    output_file.write(html_snippet)


def process_args(args):
    all_files = []

    if args.files:
        all_files = args.files
    
    elif args.folder:
        if args.recursive:
            all_files = [next_walk[0] + '/' + file for next_walk in os.walk(args.folder) for file in next_walk[2]]
        else:
            next_walk = next(os.walk(args.folder))
            all_files = [next_walk[0] + '/' + file for file in next_walk[2]]
        if args.include_json:
            all_files = [file for file in all_files if file.endswith('.js') or file.endswith('.json')]
        else:
            all_files = [file for file in all_files if file.endswith('.js')]

    all_js_files = []
    for file in all_files:
        if '/' in file:
            all_js_files.append({'name': file[file.rfind('/')+1 : ], 'path': file})
        else:
            all_js_files.append({'name': file, 'path': file})
    return all_js_files


parser = argparse.ArgumentParser(description='THis is parser!')
parser.add_argument('--projectname', required=True)
parser.add_argument('--folder')
parser.add_argument('--recursive', type=bool)
parser.add_argument('--files', nargs='+')
parser.add_argument('--include-json')
args = parser.parse_args()
files = process_args(args)

docs = [{'name': file['name'], 'data': create_file_documentation_dict(file['path'])} for file in files if file['path'].endswith('.js')]
json_docs = [{'name': file['name'], 'data': create_file_documentation_dict_json(file['path'])} for file in files if file['path'].endswith('.json')]

doc_file = init_output_file(args.projectname)

for json_documentation_dict in json_docs:
    json_documentation_to_file(doc_file, json_documentation_dict)


for documentation_dict in docs:
    js_documentation_to_file(doc_file, documentation_dict)

doc_file.close()

html_content = open(args.projectname + '.html', 'r').read()
pdfkit.from_file(args.projectname + '.html', 'asdasd.pdf')

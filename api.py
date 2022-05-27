from flask import Flask, request, jsonify
import psycopg2
import requests
import sys
from json import load
from time import sleep

def get_json(path):
    with open(path) as json_file:
        data = load(json_file)
        return data

def remove_duplicates_maintain_order(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]

def get_table(request, table):
    args_original = request.args
    args = {}
    for key in args_original.keys():
        pure_key = key.split('.')[0]
        if '~' not in args_original[key]:
            args[key] = {'operator':'=', 'value':args_original[key], 'vartype':vartype[pure_key.split('_')[0]]}
        else:
            splitlist = args_original[key].split('~')
            operator = splitlist[1].replace('neq', '!=').replace('gtet', '>=').replace('gt', '>').replace('ltet', '<=').replace('lt', '<')
            args[key] = {'operator':operator, 'value':splitlist[-1], 'vartype':vartype[pure_key.split('_')[0]]}
    columns_querytext = f'{table}.*'
    joins_querytext = []
    where_querytext = ''
    prefix = ''

    for key in args.keys():
        if where_querytext != '':
            if '.ormode' in key:
                where_querytext = where_querytext + ' OR '
            else:
                where_querytext = where_querytext + ' AND '
        else:
            where_querytext = ' '

        is_synthetic_keyword = key.split('.')[0] in keywords_synthetic.keys()
        if not is_synthetic_keyword:
            pure_key = key.split('.')[0]
            needs_join = not(pure_key in table_columns[table.replace('"', '')])
            if needs_join:
                for possible_table in table_columns.keys():
                    if pure_key in table_columns[possible_table]:
                        tabletojoin = possible_table
                        prefix = tabletojoin + '.'
                joins_querytext = joins_querytext + jointable[table.replace('"','')][tabletojoin]
                columns_querytext = columns_querytext + f', {prefix}{pure_key.split("_")[0]} AS {pure_key}'
        else:
            pure_key_name = key.split('.')[0]
            needs_join = not(keywords_synthetic[pure_key_name][1]==table)
            pure_key = keywords_synthetic[pure_key_name][0]
            columns_querytext = columns_querytext + f', {pure_key} AS {pure_key_name}'
            if needs_join:
                joins_querytext = joins_querytext + jointable[table.replace('"','')][keywords_synthetic[pure_key_name][1]]
        if args[key]['vartype'] == 'string' or args[key]['vartype'] == 'timestamp':
            where_querytext = where_querytext + prefix + pure_key.split('_')[0] + args[key]['operator'] + "'" + args[key]['value'] + "'"
        elif args[key]['vartype'] == 'int':
            where_querytext = where_querytext + prefix + pure_key.split('_')[0] + args[key]['operator'] + args[key]['value']

    if where_querytext != '':
        where_querytext = "WHERE " + where_querytext

    joins_querytext = remove_duplicates_maintain_order(joins_querytext)
    joins_querytext = " ".join(joins_querytext)
    querytext = f'SELECT {columns_querytext} FROM {table} {joins_querytext} {where_querytext};'
    print(f'querytext = {querytext}', file=sys.stderr)
    cur.execute(querytext)
    results = cur.fetchall()
    results = list(dict.fromkeys(results)) # remove duplicates

    return jsonify(results)


def try_connection_multiple_times(atempts_left = 6):
    if atempts_left == 0:
        return None
    try:
        conn = psycopg2.connect(host='db', database='postgres', user='postgres', password='postgres')
    except psycopg2.OperationalError as e:
        wait_s = 8-atempts_left
        if atempts_left != 6:
            print(f'Failed to connect to postgres. Attempts left={atempts_left}. Waiting {wait_s}s until next attempt.', file=sys.stderr)
        sleep(wait_s)
        conn = try_connection_multiple_times(atempts_left - 1)
    return conn

app = Flask(__name__)
conn = try_connection_multiple_times()
if conn is None:
    raise Exception("It was not possible to connect to the postgres database")

cur = conn.cursor()

variables = get_json('variables.json')

table_columns = variables['table_columns']
keywords_synthetic = variables['keywords_synthetic']
vartype = variables['vartype']
jointable = variables['jointable']

@app.route('/query', methods=['GET'])
def get_query():
    args = request.args
    adapted_text = args["text"].replace('divided_by', r'/').replace('asterisk', r'*').replace('equals', '=').replace('plus_sign', '+').replace('comma', ',').replace('quote', '"')
    print(f'adapted_text = {adapted_text}', file=sys.stderr)
    try:
        cur.execute(adapted_text+';')
    except psycopg2.errors.SyntaxError as e:
        return f'Problem with the adapted_text={adapted_text}'

    results = cur.fetchall()
    return jsonify(results)

@app.route('/args', methods=['GET'])
def get_test_args():
    args = request.args
    return jsonify(args)

@app.route('/exams', methods=['GET'])
def get_exam():
    return get_table(request, 'exam')

@app.route('/patients', methods=['GET'])
def get_patient():
    return get_table(request, 'patient')

@app.route('/physicians', methods=['GET'])
def get_physician():
    return get_table(request, 'physician')

@app.route('/orders', methods=['GET'])
def get_order():
    return get_table(request, '"order"')

@app.route('/status', methods=['GET'])
def get_status():
    if conn.closed == 0:
        return 'connection with the database is: up\n'
    return 'connection with the database is: down\n'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

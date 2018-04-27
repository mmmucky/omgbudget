#!/usr/bin/python

import csv
import datetime
from dateutil.parser import parse
from datetime import date
import json
import os
import re
import sys
import yaml
from collections import defaultdict
import banktransactions
import readline

def input_with_prefill(prompt, text):
    def hook():
        readline.insert_text(text)
        readline.redisplay()
    readline.set_pre_input_hook(hook)
    result = raw_input(prompt)
    readline.set_pre_input_hook()
    return result

def get_classification(item, classification_map):
    if item == '':
        return 'pending'
    for regex, classification in classification_map:
        if regex.match(item):
            return classification
    return 'unknown'

def get_bucket(buckets, date):
    for bucket in buckets:
        if bucket.contains(date):
            return bucket
    return None

# Load bucket and budget info
with open('data-out.yml', 'r') as stream:
    try:
        data = yaml.load(stream)
        defined_buckets = data['buckets']
        monthly_budget = data['budget']
        ignore_transactions = data['ignore_transactions']
        buckets_to_normalize = data['normalize_buckets']
    except yaml.YAMLError as exc:
        print(exc)

# Load budget
budget = banktransactions.Budget()
for k, v in monthly_budget.items():
    budget.add_budget_item(k,v)


# compile strings into regexes
# a list of tuples of the form (company_regex, bucket)
cost_bucket_map = []
for bucket, companies in defined_buckets.items():
    cost_bucket_map += [(re.compile(company), bucket) for company in companies]

report_unclassified = False

# Scan data to get a transaction date range
earliest_trans = None
latest_trans = None
for transaction in banktransactions.transaction_reader(sys.argv[1]):
    if not earliest_trans or transaction.date < earliest_trans:
        earliest_trans = transaction.date
    if not latest_trans or transaction.date > latest_trans:
        latest_trans = transaction.date

# Generate buckets and apply budget
today = datetime.datetime.today()
#buckets = banktransactions.generate_quarterly_buckets2(earliest_trans, latest_trans)
buckets = banktransactions.generate_monthly_buckets(earliest_trans, latest_trans)

#buckets = banktransactions.generate_quarterly_buckets(8)
#buckets = banktransactions.generate_weekly_buckets()
#buckets = banktransactions.generate_monthly_buckets(4)
for bucket in buckets:
    bucket.set_budget(budget)
    bucket.set_transaction_start_end_dates(earliest_trans, latest_trans)


unknown_transactions = []

# track the first and last transaction to detect buckets that are partially or not covered by transactions.
earliest_trans = None
latest_trans = None

# Read transactions, classify, and add to buckets.
for transaction in banktransactions.transaction_reader(sys.argv[1]):
    if not earliest_trans or transaction.date < earliest_trans:
        earliest_trans = transaction.date
    if not latest_trans or transaction.date > latest_trans:
        latest_trans = transaction.date

    b = get_bucket(buckets, transaction.date)
    if b:
        classification = get_classification(transaction.party, cost_bucket_map)
        if classification == 'unknown':
            unknown_transactions.append(transaction)
        transaction.set_classification(classification)
        b.add_transaction(transaction)

print('The following expenses have been normalized to a per-bucket average:')
for expense in buckets_to_normalize:
    print('    - {}'.format(expense))
    banktransactions.normalize_expense(expense, buckets)

for bucket in buckets:
    if bucket.money_in or bucket.money_out:
        print('')
        bucket.summary(report_unclassified)
        print('')

if report_unclassified:
    for trans in unknown_transactions:
        # TODO: This shouldn't be a string match, it should be a regex match, I guess.
        if trans.amount > -100 or trans.party in ignore_transactions:
            continue
        print ''
        print '{} {} {}'.format(trans.date, trans.party, trans.amount)
        print '  '.join(defined_buckets.keys())
        #regex = raw_input('regex: ')
        regex = input_with_prefill('regex: ', trans.party)
        key = raw_input('bucket: ')
        if key == 'ignore':
            ignore_transactions.append(regex)
        if regex == 'done':
            break
        if regex == 'stop':
            break
        if regex != 'no':
            print('updating...')
            try:
                defined_buckets[key].append(regex)
            except:
                pass
    
with open('data-out.yml', 'w') as outfile:
    outfile.write(yaml.dump({'buckets': defined_buckets, 'budget': monthly_budget, 'normalize_buckets': buckets_to_normalize, 'ignore_transactions': ignore_transactions}))


#!/usr/bin/env python3

import argparse
import csv
import datetime
#from dateutil.parser import parse
#import dateutil.parser
from datetime import date
import json
import os
import re
import readline
import sys
import yaml
from collections import defaultdict

import banktransactions

DEFAULT_BUDGET_FILE = 'data.yml'

def readline_input(prompt, prefill=''):
   readline.set_startup_hook(lambda: readline.insert_text(prefill))
   try:
      return input(prompt)  # or raw_input in Python 2
   finally:
      readline.set_startup_hook()

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

def add_classification(data, transaction):
    existing_expense_buckets = list(data['expense_buckets'].keys())
    print('S Skip this expense.')
    expense_bucket = None
    valid_re_provided = False
    while expense_bucket != 'S':
        for i in range(len(existing_expense_buckets)):
            print('{} {}'.format(i, existing_expense_buckets[i]))
        expense_bucket = readline_input('Choose an expense bucket[{}-{}] for "{}": '.format(0, len(existing_expense_buckets)-1, transaction.party))
        if expense_bucket == 'S' or expense_bucket == 's':
            expense_bucket = 'S'
            continue
        while not valid_re_provided:
            expense_regex = readline_input('Choose a regex for "{}": '.format(transaction.party), transaction.party)
            try:
                test_re = re.compile(expense_regex)
            except:
                continue
            if test_re.match(transaction.party):
                data['expense_buckets'][existing_expense_buckets[int(expense_bucket)]].append(expense_regex)
                f = open(budget_file, "w")
                yaml.dump(data, f)
                f.close()
                vaid_re_provided = True
                expense_bucket = 'S'
                break
            else:
                print('invalid RE provided... Try again.')
    if valid_re_provided:
        print('regex: {}'.format(expense_regex))
    print('returning from add classification')

def generate_quarterly_buckets(num_quarters):
    previous_quarter_map = {}
    buckets = []
    today = datetime.datetime.today()
    if today.month < 4:
        start_date = today.replace(month=1, day=1).date()
        end_date = start_date.replace(month=4) - datetime.timedelta(days=1)
        description = 'Quarter :     Q1 {}'.format(today.year)
    elif today.month < 7:
        start_date = today.replace(month=4, day=1).date()
        end_date = start_date.replace(month=7) - datetime.timedelta(days=1)
        description = 'Quarter :     Q2 {}'.format(today.year)
    elif today.month < 10:
        start_date = today.replace(month=7, day=1).date()
        end_date = start_date.replace(month=10) - datetime.timedelta(days=1)
        description = 'Quarter :     Q3 {}'.format(today.year)
    else:
        start_date = today.replace(month=10, day=1).date()
        end_date = start_date.replace(month=12, day=31)
        description = 'Quarter :     Q4 {}'.format(today.year)

    while num_quarters > 0:
        buckets.append(banktrasactions.Bucket(start_date, end_date, description, budget=budget))

        if start_date.month == 1:
            year = start_date.year -1
        else:
            year = start_date.year

        if start_date.month == 1:
            start_date = start_date.replace(year=year, month=10, day=1)
            end_date = start_date.replace(year=year, month=12, day=31)
            description = 'Quarter :     Q4 {}'.format(start_date.year)
        elif start_date.month == 4:
            start_date = start_date.replace(year=year, month=1, day=1)
            end_date = start_date.replace(month=4) - datetime.timedelta(days=1)
            description = 'Quarter :     Q1 {}'.format(start_date.year)
        elif start_date.month == 7:
            start_date = start_date.replace(year=year, month=4, day=1)
            end_date = start_date.replace(month=7) - datetime.timedelta(days=1)
            description = 'Quarter :     Q2 {}'.format(start_date.year)
        elif start_date.month == 10:
            start_date = start_date.replace(year=year, month=7, day=1)
            end_date = start_date.replace(year=year, month=12, day=31)
            description = 'Quarter :     Q3 {}'.format(start_date.year)
#        if first_of_month.month < 12:
#            last_of_month = first_of_month.replace(month=first_of_month.month+1) - datetime.timedelta(days=1)
#        else:
#            last_of_month = date(year=first_of_month.year+1, month=1, day=1) - datetime.timedelta(days=1)
        num_quarters -= 1
    return buckets

def generate_yearly_buckets(count):
    buckets = []
    today = datetime.datetime.today()
    first_of_year = today.replace(day=1, month=1).date()
    while count > 0:
        last_of_year = first_of_year.replace(day=31, month=12)
        description = 'Year:      {}'.format(first_of_year.strftime('%Y'))
        buckets.append(banktransactions.Bucket(first_of_year, last_of_year, description, budget=budget))
        first_of_year = first_of_year - datetime.timedelta(days=1)
        first_of_year = first_of_year.replace(day=1, month=1)
        count -= 1
    return buckets

def generate_monthly_buckets(num_months):
    buckets = []
    today = datetime.datetime.today()
    #today = datetime.datetime(year=2018, month=12, day=5)
    first_of_month = today.replace(day=1).date()
    while num_months > 0:
        if first_of_month.month < 12:
            last_of_month = first_of_month.replace(month=first_of_month.month+1) - datetime.timedelta(days=1)
        else:
            last_of_month = date(year=first_of_month.year+1, month=1, day=1) - datetime.timedelta(days=1)
        description = 'Month:      {}'.format(first_of_month.strftime('%B %Y'))
        description = first_of_month.strftime('%Y-%m-%d')
        buckets.append(banktransactions.Bucket(first_of_month, last_of_month, description, budget=budget))
        first_of_month = first_of_month - datetime.timedelta(days=1)
        first_of_month = first_of_month.replace(day=1)
        num_months -= 1
    return buckets

def generate_weekly_buckets():
    today = datetime.datetime.today()
    weekday = today.weekday()
    week_end_delta = datetime.timedelta(days=6-weekday)
    end_of_week = today + week_end_delta
    prev_week = ''
    buckets = []
    for i in range(12):
        prev_week = end_of_week - datetime.timedelta(weeks=1)
        buckets.append(banktransactions.Bucket(prev_week, end_of_week-datetime.timedelta(days=1), '', budget=budget))
        end_of_week = prev_week
    return buckets

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--budget', help='Budget definition file')
    parser.add_argument('--transactions-file', '-t', help='Westpac Transactions CSV', required=True)
    parser.add_argument('--classify', '-c', action='store_true', help='Offer to add regexes for unclassified transactions')
    parser.add_argument('--format', default='standard', help='Output format: standard, csv')
    args = parser.parse_args()

    # TODO Move data to data file
    shared_expense_buckets = ['groceries', 'rent', 'houseware', 'medical', 'bills/power', 'bills/other', 'bills/insurance', 'bills/internet',
                      'bills/natural gas', 'bills/phone', 'transport/fuel', 'travel', 'takeaway', 'dinner-out']

    # Load budget data from file
    if args.budget:
        budget_file = args.budget
    else:
        budget_file = DEFAULT_BUDGET_FILE
    with open(budget_file, 'r') as stream:
        try:
            data = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            sys.exit(1)
    budget = banktransactions.Budget()
    for k, v in data['monthly_budget'].items():
        budget.add_budget_item(k,v)

    # compile company name regex strings into regexes
    # a list of tuples of the form (company_regex, bucket)
    cost_bucket_map = []
    for bucket, companies in data['expense_buckets'].items():
        cost_bucket_map += [(re.compile(company), bucket) for company in companies]

    # Calculate bucket(s)
    today = datetime.datetime.today()
    #buckets = generate_quarterly_buckets(8)
    #buckets = generate_weekly_buckets()
    buckets = generate_monthly_buckets(13)
    #buckets = generate_yearly_buckets(5)

# Custom one-year bucket
#    today = datetime.datetime.today()
#    #start = today.replace(day=1, month=1).date() - datetime.timedelta(days=365)
#    start = today - datetime.timedelta(days=365)
#    end = start + datetime.timedelta(days=365*2)
#    description = 'Custom bucket'
#    buckets = [banktransactions.Bucket(start, end, description, budget=budget)]

    #search_buckets(buckets, datetime.date(2017,12,31))
    #Date,Amount,Other Party,Description,Reference,Particulars,Analysis Code

    # Read transactions from csv
    # TODO: Detect date format automatically.
    # TODO: regex to ignore specific trasactions.
    for transaction in banktransactions.transaction_reader(args.transactions_file):
            # search for a bucket that contains the date of this transaction
            b = get_bucket(buckets, transaction.date)
            if b:
                # get the classification for this transaction and add it to the bucket
                classification = get_classification(transaction.party, cost_bucket_map)
                transaction.set_classification(classification)
                b.add_transaction(transaction)
            else:
                print('Failed to locate bucket for:')
                print(transaction)

    #        if classification == 'unknown' and report_unclassified:
    #            #print 'unknown {}: {} {}'.format(bucket_num, -1*int(float(row[1])), row[2])
    #            print '{} {}'.format(-1*int(float(row[1])), expense)

    if data['buckets_to_normalize']:
        print('The following expenses have been normalized to a per-bucket average:')
        # bills, medical, rent paycheck
        for expense in data['buckets_to_normalize']:
            print('    - {}'.format(expense))
            banktransactions.normalize_expense(expense, buckets)

    report_unclassified = False
    classify_unclassified = args.classify
    if classify_unclassified:
        report_unclassified = True
    for bucket in buckets:
        if bucket.money_in or bucket.money_out:
            print('')
            bucket.summary(format=args.format)
            if report_unclassified:
                unclassified_txns = bucket.get_transactions_by_classification('unknown')
                sorted_txns = sorted(unclassified_txns, key=lambda t: t.amount)
                for txn in sorted_txns:
                    print('Unclassified transaction: {:20} {}'.format(txn.party, txn.amount))
                    if classify_unclassified:
                        print('Adding classification for: {}'.format(txn))
                        add_classification(data, txn)

            print('')

#    tbass_annual_report = True
#    if tbass_annual_report == True:
#        report_yearly = ['rent', 'bills/power', 'bills/internet', 'bills/natural gas']
#        report_all = ['work']
#        filter_txns = ['GOOGLE', 'Catalyst', 'Mavis']
#        for bucket in buckets:
#            if bucket.money_in or bucket.money_out:
#                for yearly_report_item in report_yearly:
#                    txns = bucket.get_transactions_by_classification(yearly_report_item)
#                    total = 0
#                    for txn in txns:
#                        total -= txn.amount
#                    print('{:20}   {:20} transactions, totaling ${}'.format(yearly_report_item, len(txns), total))
#
#                for report_all_item in report_all:
#                    txns = bucket.get_transactions_by_classification(report_all_item)
#                    for txn in txns:
#                        skip = False
#                        for f in filter_txns:
#                            if f in txn.party:
#                                skip=True
#                        if not skip:
#                            print(txn)
#
#                txns = bucket.get_transactions_by_classification('paycheck')
#                for txn in txns:
#                    skip = False
#                    for f in filter_txns:
#                        if f in txn.party:
#                            skip=True
#                    if not skip:
#                        print(txn)
#                    #print('{:20}   {:20} transactions, totaling ${}'.format(yearly_report_item, len(txns), total))
#

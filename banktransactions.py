#!/usr/bin/python

import csv
import datetime
#from dateutil.parser import parse
from datetime import date
import json
import os
import re
import sys
#import yaml
from collections import defaultdict

def red(text):
    if sys.stdout.isatty() and not os.getenv('ANSI_COLORS_DISABLED'):
        text = '\033[31m' + text + '\033[0m'
    return text

def yellow(text):
    if sys.stdout.isatty() and not os.getenv('ANSI_COLORS_DISABLED'):
        text = '\033[33m' + text + '\033[0m'
    return text

def green(text):
    if sys.stdout.isatty() and not os.getenv('ANSI_COLORS_DISABLED'):
        text = '\033[32m' + text + '\033[0m'
    return text


class Budget(object):
    def __init__(self):
        self.budget_data = {}

    def add_budget_item(self, item, monthly_amount):
        self.budget_data[item] = float(monthly_amount)

    def get_budget(self, item):
        try:
            return self.budget_data[item]
        except:
            return 1

    def __repr__(self):
        return json.dumps(self.budget_data, indent=True)

class Bucket(object):
    # TODO: take data start and end at bucket creation to define partial bucket
    def __init__(self, start, end, description, budget=None):
        self.start = start
        if isinstance(start, datetime.datetime):
            self.start = start.date()
        self.end = end
        if isinstance(end, datetime.datetime):
            self.end = end.date()
        self.bucket_length_in_days = (self.end - self.start).days + 1

        # If data does not cover entire bucket, declare this via set_transaction_start_end_dates()
        self.partial_data = False 
        self.data_start = self.start
        self.data_end = self.end
        self.data_length_in_days = (self.data_end - self.data_start).days + 1
        
        self.description = description
        self.transactions = []
        self.money_in = 0
        self.money_out = 0
        self.bucket_totals = defaultdict(int)
        self.budget = budget

    def set_budget(self, budget):
        self.budget = budget

    def set_transaction_start_end_dates(self, start, end):
        ''' declare when the first and last transactions are so as to detect partial buckets'''
        if start > self.data_start:
            self.data_start = start
            self.partial_data = True
        if end < self.data_end:
            self.data_end = end
            self.partial_data = True
        self.data_length_in_days = (self.data_end - self.data_start).days + 1


    def add_transaction(self, transaction):
        self.transactions.append(transaction)
        if transaction.amount < 0:
            self.money_out -= transaction.amount
        if transaction.amount > 0:
            self.money_in += transaction.amount
        self.bucket_totals[transaction.classification] += transaction.amount

    def contains(self, d):
        if isinstance(d, datetime.datetime):
            d = d.date()
        return self.start <= d <= self.end

    def data_coverage(self):
        return self.data_length_in_days / float(self.bucket_length_in_days)

    def summary(self, report_unclassified=False):
#        #TODO: Don't use today as a reference.. use start and end of data.
#        today = datetime.datetime.today().date()
#        days_into_range = (today - self.start).days
#        if self.partial:
            #print('days:    {}'.format(length_in_days))
#            percent =  (days_into_range / float(length_in_days))
            #print('percent:  {}'.format(int(100*percent)))
        print(self.description)
        print('Dates:        {} - {}'.format(self.start, self.end))
        print('Transactions: {}'.format(len(self.transactions)))
        print('Money In:     {}'.format(self.money_in))
        print('Money Out:    {}'.format(self.money_out))
        print('Net:          {}'.format(self.money_in - self.money_out))

        print('data coverage:{}%'.format(round(100*self.data_coverage())))
        for category, total in sorted(self.bucket_totals.iteritems(), key=lambda(k,v):(v,k)):
            #if monthly_budget[category] != 1:
            if self.budget and self.budget.get_budget(category) != 1:
                #print 'budget exists for {}: {} per month'.format(category, monthly_budget[category])
                #print 'daily budget is {}'.format(monthly_budget[category]/29.53)
                #print '{} days times daily budget of {} = {}'.format(length_in_days, monthly_budget[category]/29.53, (monthly_budget[category]/29.53)* length_in_days)
                budget_amount = (self.budget.get_budget(category)/29.53)* self.data_length_in_days
            else:
                budget_amount = 1
            over_under = int(100*(-1*total - budget_amount)/budget_amount)
            message = '{:20} {} (budget: {} {}%)'.format(category, total, int(budget_amount), over_under)
            if budget_amount <= 1:
                message = '{:20} {} (No budget defined)'.format(category, total)
                print(message)
            elif -1*total > budget_amount:
                print(red(message))
            elif -1*total <= budget_amount:
                print(green(message))
#        if report_unclassified:
#            for transaction in self.transactions:
#                if transaction.classification == 'unknown' and abs(transaction.amount) > 50:
#                    print transaction
        
    def __repr__(self):
        return 'start: {} end: {} transactions: {}'.format(self.start, self.end, len(self.transactions))

class Transaction(object):
    def __init__(self, date, party, amount, classification = 'unknown'):
        self.date = date
        self.party = party
        self.amount = float(amount)
        self.classification = classification

    def set_classification(self, classification):
        self.classification = classification

    def __repr__(self):
        return '{} {} ({}) {}'.format(self.date, self.classification, self.party, self.amount)
        
##Date,Amount,Other Party,Description,Reference,Particulars,Analysis Code


# Process transactions
def transaction_reader(transaction_csv):
    with open(transaction_csv, 'rb') as csvfile:
        cvsreader = csv.reader(csvfile, delimiter=',')
        for row in cvsreader:
            if not row or row[0] == 'Date':
                continue
            expense = row[2]
            expense = re.sub('^[0-9]* ', '', expense)
            expense = re.sub(' [0-9]*$', '', expense)
            row[2] = expense
    
            yield Transaction(datetime.datetime.strptime( row[0], "%d/%m/%Y" ).date(), row[2], row[1])

def normalize_expense(expense, buckets):
    '''This is a two phase normalization function'''
    # First, scan all buckets, locating the earliest and latest buckets with transactions
    # Remove transactions for this expense
    total = 0
    cumulative_bucket_coverage = 0
    first_sighting = None
    last_sighting = None
    for bucket in buckets:
        for transaction in list(bucket.transactions):
            # This bucket has at least one transaction: mark it as a possible start/end for normalization
            if not first_sighting or bucket.start < first_sighting:
                first_sighting = bucket.start
            if not last_sighting or bucket.end > last_sighting:
                last_sighting = bucket.end

            if transaction.classification == expense:
                bucket.transactions.remove(transaction)
                total += transaction.amount
                if transaction.amount < 0:
                    bucket.money_out += transaction.amount
                if transaction.amount > 0:
                    bucket.money_in -= transaction.amount
                bucket.bucket_totals[transaction.classification] -= transaction.amount
#                buckets_with_this_expense.append(bucket)

    # count bucket coverage for buckets between first and last sighting
    for bucket in buckets:
        if first_sighting and last_sighting and bucket.start >= first_sighting and bucket.end <= last_sighting:
            cumulative_bucket_coverage += bucket.data_coverage()
            print('adding {} to cumulative bucket coverage.'.format(bucket.data_coverage()))

    #average_cost = round(total / float(normalized_bucket_count), 2)
    # add synthetic transactions with weights according to data coverage of each bucket
    for bucket in buckets:
        if first_sighting <= bucket.start <= bucket.end <= last_sighting:
            bucket.add_transaction(Transaction(bucket.start, 'TODO', round((total / float(cumulative_bucket_coverage))*bucket.data_coverage() , 2), expense))

def _quarter_from_date(d):
    ''' Given a date, return which quarter it belongs to '''
    months_to_quarter = {tuple([1,2,3]): 1, tuple([4,5,6]): 2, tuple([7,8,9]): 3, tuple([10,11,12]): 4}

    # we do replacements to let datetime take care of leap years.
    for months, quarter in months_to_quarter.items():
        if d.month in months:
#            print('found that month {} is in quarter {}'.format(d.month, quarter))
            start_date = d.replace(month=1 + (quarter-1)*3, day=1)
#            print('quarter start: {}'.format(start_date))
            if d.month < 10:
                # BUG: can't just replace month
                #end_date = d.replace(month=1 + quarter*3) - datetime.timedelta(days=1)
                end_date = d.replace(month=1 + quarter*3, day=1) - datetime.timedelta(days=1)
#                print('quarter end: {}'.format(end_date))
            else:
                end_date = d.replace(month=12, day=31)
            return (quarter, start_date, end_date)


def generate_quarterly_buckets2(data_start, data_end):
    previous_quarter_map = {}
    buckets = []
    quarter, start_date, end_date = _quarter_from_date(data_end)
    description = 'Quarter :     Q{} {}'.format(quarter, start_date.year)
    buckets.append(Bucket(start_date, end_date, description))
    # go back in time generating buckets until we generate a bucket that won't include any data
    while start_date > data_start:
        quarter, start_date, end_date = _quarter_from_date(start_date - datetime.timedelta(days=1))
        description = 'Quarter :     Q{} {}'.format(quarter, start_date.year)
        buckets.append(Bucket(start_date, end_date, description))
    return buckets

def _month_from_date(d):
    ''' Given a date, return which month it belongs to '''
    months_to_quarter = {tuple([1,2,3]): 1, tuple([4,5,6]): 2, tuple([7,8,9]): 3, tuple([10,11,12]): 4}

    start = d.replace(day=1)
    if start.month < 12:
        end = start.replace(month=start.month+1) - datetime.timedelta(days=1)
    else:
        end = date(year=start.year+1, month=1, day=1) - datetime.timedelta(days=1)
    month = start.strftime("%B")
    return month, start, end

def generate_monthly_buckets(data_start, data_end):
    buckets = []
    #TODO: Don't use today as a reference.. use start and end of data.
    #today = datetime.datetime(year=2018, month=12, day=5)
    month, start_date, end_date = _month_from_date(data_end)
    print data_end
    description = 'Month:        {} {}'.format(month, start_date.year)
    buckets.append(Bucket(start_date, end_date, description))
    # go back in time generating buckets until we generate a bucket that won't include any data
    while start_date > data_start:
        month, start_date, end_date = _month_from_date(start_date - datetime.timedelta(days=1))
        description = 'Month:        {} {}'.format(month, start_date.year)
        buckets.append(Bucket(start_date, end_date, description))
    return buckets


# TODO: Broken
def generate_weekly_buckets():
    #TODO: Don't use today as a reference.. use start and end of data.
    today = datetime.datetime.today()
    weekday = today.weekday()
    week_end_delta = datetime.timedelta(days=6-weekday)
    end_of_week = today + week_end_delta
    prev_week = ''
    buckets = []
    for i in range(12):
        prev_week = end_of_week - datetime.timedelta(weeks=1)
        buckets.append(Bucket(prev_week, end_of_week-datetime.timedelta(days=1), ''))
        end_of_week = prev_week
    return buckets


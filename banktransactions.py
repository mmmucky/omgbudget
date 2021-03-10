#!/usr/bin/python3

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
    """
    A class to map budgeted items to monthly dollar amounts.
    This could probably be replaced by a defaultdict.

    """
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
    """
    A Class to represent a connection of transactions that were processed
    during a particular period of time.  Adding a transaction to a bucket
    updates net money in and per-expense-bucket totals

    An optional budget can be defined.
    """
    def __init__(self, start, end, description, budget=None):
        self.start = start
        if isinstance(start, datetime.datetime):
            self.start = start.date()
        self.end = end
        if isinstance(end, datetime.datetime):
            self.end = end.date()
        today = datetime.datetime.today().date()
        if self.start <= today <= self.end:
            self.partial = True
        else:
            self.partial = False

        self.description = description
        self.transactions = []
        self.money_in = 0
        self.money_out = 0
        self.bucket_totals = defaultdict(int)
        self.budget = budget

    def set_budget(self, budget):
        self.budget = budget

    def add_transaction(self, transaction):
        self.transactions.append(transaction)
        #TODO Why not just calculate these values when requested?
        if transaction.amount < 0:
            self.money_out -= transaction.amount
        if transaction.amount > 0:
            self.money_in += transaction.amount
        self.bucket_totals[transaction.classification] += transaction.amount

    def contains(self, test_date):
        """Return true if test_date falls inside this bucket's date range."""
        if isinstance(test_date, datetime.datetime):
            test_date = test_date.date()
        return self.start <= test_date <= self.end

    def get_transactions_by_classification(self, classification):
        """Return a list of transactions that have no classification."""
        return [txn for txn in self.transactions if txn.classification == classification]

    def summary(self, format='standard', report_unclassified=False):
        """Print a summary of this bucket"""
        today = datetime.datetime.today().date()
        days_into_range = (today - self.start).days
        length_in_days = (self.end - self.start).days + 1
        if self.partial:
            #print('days:    {}'.format(length_in_days))
            percent =  (days_into_range / float(length_in_days))
            #print('percent:  {}'.format(int(100*percent)))
        print(self.description)
        print('Dates:            {} - {}'.format(self.start, self.end))
        print('Transactions:     {}'.format(len(self.transactions)))
        print('Money In:         {}'.format(int(self.money_in)))
        print('Money Out:        {}'.format(int(self.money_out)))
        print('Money In(Net):    {}'.format(int(self.money_in - self.money_out)))
        print('')
        #print(self.bucket_totals.items())
        #TODO: port to python3.    for category, total in sorted(self.bucket_totals.items(), key=lambda(k,v):(v,k)):
        #print(sorted(self.bucket_totals, key=self.bucket_totals.get, reverse=True).items)
        sorted_keys = sorted(self.bucket_totals, key=self.bucket_totals.get)
        for category, total in [(k, self.bucket_totals[k]) for k in sorted_keys]:
        #for category, total in self.bucket_totals.items():
            #if monthly_budget[category] != 1:
            if self.budget and self.budget.get_budget(category) != 1:
                #print 'budget exists for {}: {} per month'.format(category, monthly_budget[category])
                #print 'daily budget is {}'.format(monthly_budget[category]/29.53)
                #print '{} days times daily budget of {} = {}'.format(length_in_days, monthly_budget[category]/29.53, (monthly_budget[category]/29.53)* length_in_days)
                budget_amount = (self.budget.get_budget(category)/29.53)* length_in_days
            else:
                budget_amount = 1
            if self.partial:
                #print('applying partial percent of {}'.format(percent))
                budget_amount *= percent
            over_under = int(100*(-1*total - budget_amount)/budget_amount)
            if format=='standard':
                message = '{:20} {} (budget: {} {}%)'.format(category, int(total), int(budget_amount), over_under)
                if budget_amount <= 1:
                    message = '{:20} {} (No budget defined)'.format(category, int(total))
                    print(message)
                elif -1*total > budget_amount:
                    print(red(message))
                elif -1*total <= budget_amount:
                    print(green(message))
            elif format=='csv':
                print('{},{},{}'.format(self.description, category, int(total)))

        # TODO: Split out from summary function.
        if report_unclassified:
            unclassified_transactions = [x for x in self.transactions if x.classification == 'unknown']
            sorted_transactions = sorted(unclassified_transactions, key=lambda t: t.amount)
            for txn in sorted_transactions:
                print('Unclassified transaction: {:20} {}'.format(txn.party, txn.amount))

            #for transaction in self.transactions:
            #    if transaction.classification == 'unknown' and abs(transaction.amount) > 0:
            #        print transaction

    def __repr__(self):
        return 'start: {} end: {} transactions: {}'.format(self.start, self.end, len(self.transactions))

class Transaction(object):
    """
    A class to represent a line from a Westpac CSV Transaction export
    """
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
    print(transaction_csv)
    with open(transaction_csv, newline='') as csvfile:
        cvsreader = csv.reader(csvfile, delimiter=',')
        for row in cvsreader:
            try:
                if row[0] == 'Date':
                    continue
                expense = row[2]
                expense = re.sub('^[0-9]* ', '', expense)
                expense = re.sub(' [0-9]*$', '', expense)
                row[2] = expense
                yield Transaction(datetime.datetime.strptime( row[0], "%d/%m/%Y" ).date(), row[2], row[1])
            except:
                print('Failed to parse transaction...')
                print(row)
                next

#TODO: when using old csv, we will add normalized transactions after the most recent transaction!
# Need to confine ourselves to the date range in the csv
def normalize_expense(expense, buckets):
    total = 0
#    buckets_with_this_expense = []
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
    # count buckets between first and last sighting
    normalized_bucket_count = 0
    for bucket in buckets:
        if first_sighting <= bucket.start and last_sighting >= bucket.end:
            normalized_bucket_count += 1
    average_cost = round(total / float(normalized_bucket_count), 2)
    for bucket in buckets:
        if first_sighting <= bucket.start <= bucket.end <= last_sighting:
            bucket.add_transaction(Transaction(bucket.start, 'TODO', average_cost, expense))


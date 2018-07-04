# Copyright 2018 https://github.com/urljig
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import unittest
import argparse
import sys
import functools
from decimal import Decimal

__doc__ = """A simple command-line loan calculator program."""


class PaymentCalculator:
    """Monthly interest rate is calculated by dividing the annual rate by
12.

* Let r = annual-rate / 12.
* Let P be the principal of the loan upon distribution.

Our first month's principal payment, p[1], satisfies the following
relationship:

p[1] + P * r = M

where M is our monthly payment and P * r is the interest we pay on our
total outstanding principal P. (We haven't payed them anything back
yet, and p[1] is going to be our first payment.)

In the second month our principal payment, p[2], satisfies

p[2] + (P - p[1]) * r = M

Notice this is still equal to M because we want to have the same
monthly payment every month. Where now P - p[1] is the outstanding
principal on which we pay interest. We can compute the relationship
between p[1] and p[2] from

p[1] + P * r = M = p[2] + (P - p[1]) * r

which reduces to

p[2] = (1 + r) * p[1]

We can compute a similar relationship for p[3]

p[3] = (1 + r) * p[2] = (1 + r) * (1 + r) * p[1]

And cosequently

p[i] = (1 + r)^(i - 1) * p[1]  for i >= 1

Since our total principal P is p[1] + p[2] + ... + p[m] then this sum can
be rewritten as,

p[1] +      p[2]      +       p[3]       + ... +          p[m]            = P
p[1] + p[1] * (1 + r) + p[1] * (1 + r)^2 + ... + p[1] * (1 + r)^(m - 1)   = P

Factoring p[1]:

p[1] * ( 1 + (1+r) + (1+r)^2 + ... + (1 + r)^(m - 1) )  = P

The geometric series ( 1 + (1+r) + (1+r)^2 + ... + (1 + r)^(m - 1) )
can be rewritten as

    (1 - (1 + r)^m) / (1 - (1 + r)) = ((1 + r)^m - 1) / r

We then have

p[1] = P * r / ( (1 + r)^m - 1 )

This is the closed form formula for the principal paid in the first month.

We can now also compute the total montly payment from

p[1] + P * r = M

            [             1       ]
M = P * r * [ 1 +  -------------  ]
            [      (1 + r)^m - 1  ]

    """

    def __init__(self, principal, annual_rate, payments,
                 one_time_payments=[], recurring_payments=[]):
        self.principal = principal
        self.annual_rate = annual_rate
        self.payments = payments
        self.one_time_payments = {i: amount for i, amount in one_time_payments}
        self.recurring_payments = {
            (s, o): amount for s, o, amount in recurring_payments
        }

        self._r = self.annual_rate / 1200

    def _first_month_principal(self):
        denom = ((1 + self._r)**self.payments - 1)
        return round(self.principal * self._r / denom, 2)

    def monthly_payment(self):
        pr = self.principal * self._r
        return round(self._first_month_principal() + pr, 2)

    def _extra_payments(self, i):
        rv = 0
        if i in self.one_time_payments:
            rv += self.one_time_payments[i]
        for s, o in self.recurring_payments:
            if i - s >= 0 and (i - s) % o == 0:
                rv += self.recurring_payments[(s, o)]
        return rv

    def __iter__(self):
        """Yields a 3-tuple, (principal, interest, refund), where a refund is
        issued if a one-time payment pays-off the loan and a credit
        remains.

        """
        p1 = self._first_month_principal()
        monthly_payment = self.monthly_payment()
        principal_paid = 0
        for i in range(self.payments):
            extra_pay = self._extra_payments(i)
            # Every month a standard principal and interest are paid
            # based on the calculated monthly payment.
            principal_i = round(p1 * (1 + self._r)**i, 2)
            if ((principal_paid + principal_i >= self.principal) or
                (i == self.payments - 1)):
                # Payment pays off the loan.
                final_principal = self.principal - principal_paid
                yield (final_principal,
                       round(final_principal * self._r, 2),
                       extra_pay)
                break
            principal_paid += principal_i
            interest_i = monthly_payment - principal_i

            # The remainig principal.
            P_rem = self.principal - principal_paid
            if extra_pay > P_rem:
                # If the one-time-payment pays off the loan then
                # refund any credit.
                yield (principal_i + P_rem,
                       interest_i,
                       extra_pay - P_rem)
                break
            # The new loan amount is the remaining principal less the
            # one-time-payment.
            principal_paid += extra_pay
            yield (principal_i + extra_pay, interest_i, 0)
            if principal_paid == self.principal:
                break

    def tabulate(self, file=sys.stdout):
        total_principal = 0
        total_interest = 0
        print('{:>10s}{:>10s}{:>10s}'.format(
            'Payment', 'Principal', 'Interest'))
        for i, (principal, interest, refund) in enumerate(pc):
            total_principal += principal
            total_interest += interest
            print('{:10d}{:10}{:10}'.format(i + 1, principal, interest))
            ep = self._extra_payments(i)
            if ep > 0:
                print('    Extra payments: {:.2f}'.format(ep))
            if refund > 0:
                print('Refund issued (overpayed closing): {:f}'.format(refund))
        print('Principal paid: {:10} Interest paid: {:10}'.format(
            total_principal, total_interest))


def cli():
    """Command line interface of the loan payment calculator."""

    def numeric(p):
        @functools.wraps(numeric)
        def _f(s):
            try:
                rv = Decimal(s)
                if abs(rv - round(rv, p)) > 0:
                    raise ValueError(
                        'No more than %d fractional digits expected.' % p)
                return rv
            except ValueError as e:
                raise argparse.ArgumentTypeError(*e.args)
        return _f

    def one_time_pay_type(s):
        try:
            payment_number, amount = s.split(':')
            payment_number = int(payment_number) - 1
            amount = numeric(2)(amount)
            return (payment_number, amount)
        except ValueError as e:
            raise argparse.ArgumentTypeError(*e.args)

    def recurring_pay_type(s):
        try:
            start, occurence, amount = s.split(':')
            start = int(start) - 1
            occurence = int(occurence)
            amount = numeric(2)(amount)
            return (start, occurence, amount)
        except ValueError as e:
            raise argparse.ArgumentTypeError(*e.args)

    parser = argparse.ArgumentParser(
        description='Command line loan calculator program.')
    parser.add_argument(
        'principal', type=numeric(2), help='The principal of the loan.')
    parser.add_argument(
        'rate', type=numeric(5), help='The annual interest of the loan.')
    parser.add_argument(
        'payments', type=int,
        help='Duration of the loan; the number of payments (months).')
    parser.add_argument('--one-time-payment',
                        dest='one_time_pay',
                        metavar='payment:amount',
                        type=one_time_pay_type,
                        nargs='+',
                        help='A one time payment, ex. 13:500, an \
                        extra $500 is paid at payment 13.')
    parser.add_argument('--recurring-payment',
                        dest='recurring_pay',
                        metavar='start:occurence:amount',
                        type=recurring_pay_type,
                        nargs='+',
                        help='A recurring payment, ex. 2:100 means \
                        every other month pay an extra $200.')
    parser.add_argument('--refinance',
                        metavar='payment:rate:payments')
    return parser


class TestPaymentCalculator(unittest.TestCase):
    #TODO: implement more tests...
    def setUp(self):
        self.cp = PaymentCalculator(1000, 12, 10)

    def test_first_month_interest(self):
        principal, interest, _ = next(iter(self.cp), None)
        self.assertEqual(interest, Decimal('10'))

    def test_total_principal_paid(self):
        self.assertEqual(sum([p for p, *_ in self.cp]), 1000)

    def test_amortization_table_length(self):
        self.assertEqual(len(list(self.cp)), 10)


if __name__ == '__main__':
    args = cli().parse_args()
    pc = PaymentCalculator(args.principal, args.rate, args.payments,
                           one_time_payments=args.one_time_pay or [],
                           recurring_payments=args.recurring_pay or [])
    pc.tabulate()

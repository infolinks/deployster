#!/usr/bin/env python3

import argparse
import json

from deployster.gcp.services import get_billing


def main():
    argparser = argparse.ArgumentParser(description='Attach GCP project to organization.')
    argparser.add_argument('--project-id', dest='project_id', required=True, metavar='PROJECT-ID',
                           help="the GCP project ID (eg. 'western-evening', or 'backoffice')")
    argparser.add_argument('--billing-account-id', dest='billing_account_id', required=True,
                           metavar='BILLING-ACCOUNT-ID',
                           help="the billing account ID (alpha-numeric)")
    args = argparser.parse_args()

    billing_service = get_billing().projects()
    billing_result = billing_service.updateBillingInfo(
        name='projects/' + args.project_id,
        body={"billingAccountName": f"billingAccounts/{args.billing_account_id}"}).execute()
    print(json.dumps({'result': billing_result}))


if __name__ == "__main__":
    main()

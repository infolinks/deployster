#!/usr/bin/env python3

import argparse

from deployster.gcp.services import get_billing


def main():
    argparser: argparse.ArgumentParser = argparse.ArgumentParser(description='Attach GCP project to organization.')
    argparser.add_argument('--project-id', required=True, metavar='ID', help="the alpha-numeric GCP project ID")
    argparser.add_argument('--billing-account-id', metavar='ID', help="the alpha-numeric GCP account ID")
    args = argparser.parse_args()

    billing_account_id = f"billingAccounts/{args.billing_account_id}" if args.billing_account_id else ""
    billing_service = get_billing().projects()
    billing_service.updateBillingInfo(
        name='projects/' + args.project_id,
        body={"billingAccountName": billing_account_id}).execute()


if __name__ == "__main__":
    main()

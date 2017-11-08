#!/usr/bin/env python3

import json
import sys

from deployster.gcp.services import get_billing


def main():
    params = json.loads(sys.stdin.read())

    billing_service = get_billing().projects()
    billing_result = billing_service.updateBillingInfo(
        name='projects/' + params['name'],
        body={"billingAccountName": f"billingAccounts/{params['properties']['billing_account_id']}"}).execute()
    print(json.dumps({'result': billing_result}))


if __name__ == "__main__":
    main()

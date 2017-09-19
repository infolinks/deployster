import subprocess

from util.google import get_resource_manager, get_billing, get_service_management, wait_for_resource_manager_operation
from util.google import wait_for_service_manager_operation


def setup_project(organization_id, billing_account_id, gcr_project_id, project_id):
    projects_service = get_resource_manager().projects()

    print "Looking up project '%s'..." % project_id
    result = projects_service.list(pageSize=500, filter="name:%s" % project_id).execute()
    projects = result['projects'] if 'projects' in result else []
    if len(projects) == 0:
        print "Creating Google Cloud Project '%s'..." % project_id
        result = projects_service.create(body={
            "projectId": project_id,
            "name": project_id,
            "parent": {"type": "organization", "id": str(organization_id)}
        }).execute()

        print "Waiting for project creation '%s' to complete..." % result['name']
        project = wait_for_resource_manager_operation(result)

    elif len(projects) > 1:
        raise Exception("Too many projects matching '%s' found!" % project_id)

    else:
        print "Project '%s' found" % project_id
        project = projects[0]

    # enable billing
    billing_service = get_billing().projects()
    print "Ensuring project is associated with the billing account..."
    billing_result = billing_service.updateBillingInfo(
        name='projects/' + project_id,
        body={"billingAccountName": "billingAccounts/%s" % billing_account_id}).execute()
    if not billing_result['billingEnabled']:
        raise Exception("Could not enable billing for '%s': %s" % (project_id, billing_result))

    # enable google deployment manager API
    print "Ensuring project has Google Deployment Manager API enabled..."
    service_management_service = get_service_management().services()
    op = service_management_service.enable(serviceName='deploymentmanager',
                                           body={'consumerId': 'project:' + project_id}).execute()
    wait_for_service_manager_operation(op)

    # enable logging API
    print "Ensuring project has Logging API (Stackdriver) enabled..."
    service_management_service = get_service_management().services()
    op = service_management_service.enable(serviceName='logging',
                                           body={'consumerId': 'project:' + project_id}).execute()
    wait_for_service_manager_operation(op)

    # enable monitoring API
    print "Ensuring project has Monitoring API (Stackdriver) enabled..."
    service_management_service = get_service_management().services()
    op = service_management_service.enable(serviceName='monitoring',
                                           body={'consumerId': 'project:' + project_id}).execute()
    wait_for_service_manager_operation(op)

    # allow the project's default service account to access GCR on 'infolinks-gcr' (where our docker images reside)
    # see: https://cloud.google.com/container-registry/docs/using-with-google-cloud-platform#google_container_engine
    print "Ensuring project default service account can access GCR on '%s'..." % gcr_project_id
    subprocess.check_call(
        "gcloud projects add-iam-policy-binding %s " % gcr_project_id +
        ("--member='serviceAccount:%s-compute@developer.gserviceaccount.com' " % project['projectNumber']) +
        "--role='roles/storage.objectViewer'",
        shell=True)

    # all done!
    return project

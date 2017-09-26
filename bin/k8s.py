import subprocess
import sys

import os
from jinja2 import Template
from os.path import isdir


def apply_configmap(env, config_dir, config_name, namespace_name):
    literals = ""
    if config_name in env['configurations']:
        configuration_literals = env['configurations'][config_name]
        for key, value in configuration_literals.items():
            literals = literals + " --from-literal=%s=%s" % (key, value)

    sys.stderr.write("Applying configuration map '%s' in namespace '%s'...\n" % (config_name, namespace_name))
    subprocess.check_call(
        ("kubectl create configmap %s " +
         "--namespace=%s " +
         "--save-config --dry-run --output=yaml " +
         "--from-file=%s/ %s | kubectl apply --namespace=%s -f -") % (config_name,
                                                                      namespace_name,
                                                                      config_dir,
                                                                      literals,
                                                                      namespace_name),
        shell=True)


def apply_configmaps(env, directory, namespace_name):
    # TODO: consider removing configmap support from k8s.py, instead specfiying configmaps as YAMLs
    #       when these configmaps need values from files, just use Jinja2 expressions for that
    if os.path.isdir(directory):
        for config_name in os.listdir(directory):
            config_dir = directory + '/' + config_name
            if os.path.isdir(config_dir):
                apply_configmap(env, config_dir, config_name, namespace_name)


def apply_manifest(env, manifest_file, namespace_name):
    post_processed_manifest_path = manifest_file + '.pp'
    post_processed_manifest_file = open(post_processed_manifest_path, 'w')
    post_processed_manifest_file.write(Template(open(manifest_file, 'r').read()).render(env))
    post_processed_manifest_file.close()
    sys.stderr.write("Applying manifest '%s'...\n" % manifest_file)
    cmd = "kubectl apply --namespace=%s --filename=%s" % (namespace_name, post_processed_manifest_path)
    try:
        subprocess.check_call(cmd, shell=True)
    except:
        expanded_manifest = open(post_processed_manifest_path, mode='r').read()
        sys.stderr.write("Failed applying '%s' - expanded manifest is:\n%s\n" % (manifest_file, expanded_manifest))
        raise
    os.remove(post_processed_manifest_path)


def apply_manifests(env, directory, namespace_name):
    if os.path.isdir(directory):
        for manifest_entry in sorted(os.listdir(directory)):
            manifest_file = directory + '/' + manifest_entry
            if os.path.isfile(manifest_file) and manifest_file.endswith('.yaml'):
                apply_manifest(env, manifest_file, namespace_name)


def apply_directory(env, directory, namespace_name):
    apply_configmaps(env, directory + '/configmaps', namespace_name)
    apply_manifests(env, directory + '/manifests', namespace_name)


def apply_kubernetes_state(env):
    project_id = env['project']['projectId']
    cluster_name = env['cluster']['name']
    cluster_zone = env['cluster']['zone']
    k8s = '/deploy/staging/kubernetes'

    # authenticate kubectl to cluster
    subprocess.check_call(
        "gcloud container clusters get-credentials --project %s -z %s %s" % (project_id, cluster_zone, cluster_name),
        shell=True)

    # first we make sure administrative permissions are [re]applied on the cluster
    apply_directory(env, '%s/security' % k8s, 'kube-system')

    # now apply the system manifests & configurations
    apply_directory(env, '%s/system' % k8s, 'kube-system')

    # last, apply the application manifests & configurations
    for ns in [ns for ns in os.listdir(k8s) if isdir(k8s + '/' + ns) and ns != 'system' and ns != 'security']:
        if not ns.endswith('.disabled'):
            if not subprocess.check_output("kubectl get namespace %s --ignore-not-found=true" % ns, shell=True):
                sys.stderr.write("Creating namespace '%s'...\n" % ns)
                subprocess.check_call("kubectl create namespace %s" % ns, shell=True)
            apply_directory(env, k8s + '/' + ns, ns)

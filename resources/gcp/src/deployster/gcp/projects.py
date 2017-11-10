from deployster.gcp.services import get_resource_manager


class ProjectNotFoundError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class TooManyProjectsMatchError(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def find_projects(projects_filter):
    get_resource_manager()
    result = get_resource_manager().projects().list(filter=projects_filter).execute()
    return result['projects'] if 'projects' in result else []


def find_project(project_id):
    projects = find_projects("name:" + project_id)
    if len(projects) == 0:
        raise ProjectNotFoundError(project_id)
    elif len(projects) > 1:
        raise TooManyProjectsMatchError(project_id)
    else:
        return projects[0]

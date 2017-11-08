from deployster.resource.ResourceAction import ResourceAction
from deployster.resource.ResourceStateError import ResourceStateError
from deployster.resource.ResourceStatus import ResourceStatus


class ResourceState:

    def __init__(self, resource, data):
        super().__init__()
        self._resource = resource
        self._reason = None

        if not isinstance(data, dict):
            raise ResourceStateError(f"Protocol error occurred (resource state must be an object)")
        elif 'status' not in data or not isinstance(data['status'], str):
            raise ResourceStateError(f"Protocol error occurred ('status' was not provided or is not a string)")
        elif data['status'] in ['VALID', 'STALE'] and (
                'properties' not in data or not isinstance(data['properties'], dict)):
            raise ResourceStateError(f"Protocol error occurred ('properties' expected for status '{data['status']}')")

        try:
            self._status = ResourceStatus[data['status']]
            self._properties = data['properties'] if 'properties' in data else {}
        except KeyError:
            raise ResourceStateError(f"Protocol error occurred (illegal status: {data['status']})")

        if self.status == ResourceStatus.INVALID:
            if 'reason' not in data:
                raise ResourceStateError(f"invalid resources must have 'reason' key")
            elif 'actions' in data and len(data['actions']):
                actions_count = len(data['actions'])
                raise ResourceStateError(f"invalid resources must not have actions ({actions_count} actions found)")
            else:
                self._reason = None
                self._actions = []

        elif self.status == ResourceStatus.MISSING or self.status == ResourceStatus.STALE:
            if 'reason' in data:
                raise ResourceStateError(f"missing or stale resources must not have 'reason' key")
            elif 'actions' not in data or not len(data['actions']):
                raise ResourceStateError(f"missing or stale resources must have actions")
            else:
                self._reason = None
                self._actions = [ResourceAction(self._resource, a) for a in data['actions']]

        elif self.status == ResourceStatus.VALID:
            if 'reason' in data:
                raise ResourceStateError(f"valid resources must not have 'reason' key")
            elif 'actions' in data and len(data['actions']):
                raise ResourceStateError(f"valid resources must have actions")
            else:
                self._reason = None
                self._actions = []

        else:
            raise ResourceStateError(f"unsupported resource status encountered ({self.status})")

    @property
    def resource(self):
        return self._resource

    @property
    def status(self):
        return self._status

    @property
    def reason(self):
        return self._reason

    @property
    def actions(self):
        return self._actions

    @property
    def properties(self):
        return self._properties

from typing import Any, MutableSequence


def collect_differences(desired: Any, actual: Any,
                        path: MutableSequence[str] = None, diffs: MutableSequence[str] = None):
    diffs: MutableSequence[str] = [] if diffs is None else diffs
    path: MutableSequence[str] = [] if path is None else path

    if desired is None and actual is None:
        # both are None, no difference
        return diffs

    if (desired is not None and actual is None) or (desired is None and actual is not None):
        # one is None and the other is NOT None
        diffs.append(".".join(path))
        return diffs

    if type(desired) != type(actual):
        # different types
        diffs.append(".".join(path))
        return diffs

    if isinstance(desired, dict) and isinstance(actual, dict):
        # compare dictionaries
        for key, desired_value in desired.items():
            path.append(key)
            try:
                if actual is None or key not in actual:
                    diffs.append(".".join(path))
                    continue
                actual_value = actual[key]
                collect_differences(desired_value, actual_value, path, diffs)
            finally:
                path.pop()
        return diffs

    if isinstance(desired, list) and isinstance(actual, list):
        # compare lists
        if len(desired) != len(actual):
            diffs.append(".".join(path))
        else:
            for index, desired_value in enumerate(desired):
                actual_value = actual[index]
                path.append(f"[{index}]")
                try:
                    collect_differences(desired_value, actual_value, path, diffs)
                finally:
                    path.pop()
        return diffs

    if desired != actual:
        # scalar values differ
        diffs.append(".".join(path))

    return diffs

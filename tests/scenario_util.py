import json
import os
import re
import sys
from typing import Sequence, Tuple, MutableSequence


def load_scenarios(scenarios_dir: str, scenario_pattern: str) -> Sequence[Tuple[str, dict, dict, dict]]:
    print("", file=sys.stderr)
    scenarios: MutableSequence[Tuple[str, dict, dict, dict]] = []
    for scenario_file in os.listdir(scenarios_dir):
        if re.match(scenario_pattern, scenario_file):
            file_name = os.path.join(scenarios_dir, scenario_file)
            print(f"Loading GCP project scenario '{file_name}'...", file=sys.stderr)
            with open(file_name, 'r') as f:
                scenario_data = json.loads(f.read())
                scenario_tuple = (scenario_data['description'] if 'description' in scenario_data else 'Missing',
                                  scenario_data['actual'],
                                  scenario_data['config'],
                                  scenario_data['expected'])
                scenarios.append(scenario_tuple)
    return scenarios

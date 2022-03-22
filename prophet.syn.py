import re

from pathlib import Path
from typing import List, Any, Dict

from synapser.core.data.api import RepairRequest
from synapser.core.data.results import RepairCommand
from synapser.core.database import Signal
from synapser.handlers.tool import ToolHandler
from synapser.utils.misc import match_patches


class Prophet(ToolHandler):
    """Prophet"""

    class Meta:
        label = 'prophet'
        version = ''
    
    def write_revlog_file(self, working_dir: Path, neg_tests: int, pos_tests: int):
        rev_file = working_dir.parent / "tests.revlog"

        with rev_file.open(mode="w") as rf:
            diff_cases = f"Diff Cases: Tot {neg_tests}"
            first_neg_test = pos_tests + neg_tests
            neg_tests = ' '.join([str(i) for i in range(pos_tests + 1, first_neg_test + 1)])
            pos_cases = f"Positive Cases: Tot {pos_tests}"
            pos_tests = ' '.join([str(i) for i in range(1, pos_tests + 1)])
            reg_cases = "Regression Cases: Tot 0"
            rf.write(f"-\n-\n{diff_cases}\n{neg_tests}\n{pos_cases}\n{pos_tests}\n{reg_cases}\n")

        return rev_file

    def write_config_file(self, rev_file: Path, working_dir: Path, manifest_files: list, build_cmd: str, test_cmd: str):
        config_file = working_dir.parent / Path('run.conf')

        with config_file.open(mode="w") as cf:
            rev_str = f"revision_file={rev_file}"
            src_dir = f"src_dir={working_dir}"
            test_dir = f"test_dir={working_dir.parent / 'tests'}"
            loc = "localizer=profile"
            target_file = f"bugged_file={manifest_files[0]}"
            cf.write(f"{rev_str}\n{src_dir}\n{test_dir}\nbuild_cmd={build_cmd}\ntest_cmd={test_cmd}\n{target_file}\n{loc}")

        return config_file

    def repair(self, signals: dict, repair_request: RepairRequest) -> RepairCommand:
        self.repair_cmd.add_arg(opt='-dump-passed-candidate', arg=str(repair_request.working_dir.parent / 'passed.txt'))
        self.repair_cmd.add_arg(opt='-r', arg=str(repair_request.working_dir / 'workdir'))
        rev_file = self.write_revlog_file(repair_request.working_dir, neg_tests=repair_request.args['neg_tests'], pos_tests=repair_request.args['pos_tests'])
        config_file = self.write_config_file(repair_request.working_dir, repair_request.manifest, rev_file, signal["build_cmd"], signal["test_cmd"])
        self.repair_cmd.add_arg(opt=str(config_file), arg='')

        return self.repair_cmd
    
    def build(self):
        # TODO: implement
        pass
    
    def test(self):
        # TODO: implement
        pass

    def get_patches(self, working_dir: str, target_files: List[str], **kwargs) -> Dict[str, Any]:
        # TODO: implement

        return {}

    def parse_extra(self, extra_args: List[str], signal: Signal) -> str:
        """
            Parses extra arguments in the signals.
        """
        return ""


def load(nexus):
    nexus.handler.register(Prophet)

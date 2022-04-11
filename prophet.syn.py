import re
import subprocess
import getopt

from os import chdir, getcwd, path, environ, pardir, chmod
from sys import argv
from shutil import copyfile
from pathlib import Path
from typing import List, Any, Dict

from synapser.core.data.api import RepairRequest
from synapser.core.data.results import RepairCommand
from synapser.core.database import Signal
from synapser.handlers.tool import ToolHandler
from synapser.utils.misc import match_patches
from synapser.core.exc import CommandError
from synapser.handlers.api import APIHandler


def write_sh_file(workdir, cmd, name):
#    parent_dir = path.abspath(path.join(workdir, pardir))
#    build_cmd = "python3 {cb_repair} compile -wd {wd} -cn None -B {pd}/patches --gcc --exit_err -l {wd}/clog.txt".format(
#        cb_repair=environ["CBREPAIR"], wd=workdir, pd=parent_dir)
    sh_script = "#!/bin/bash\n" + cmd + " $@"
#    makefile = ".PHONY: do_script\n\ndo_script:\n\t./build.sh\n\nprerequisites: do_script\n\ntarget: prerequisites\n"
    file_path = workdir / name
#    makefile_path = workdir / "Makefile"

    with open(file_path, "w") as fp:
        fp.write(f"{sh_script}\n")
#        mfp.write(makefile)

    chmod(file_path, 0o755)
#    chmod(makefile_path, 0o755)
    return file_path


def write_config_file(rev_file: Path, working_dir: Path, src_dir: Path, test_dir: Path, manifest_files: list, build_cmd: str, test_cmd: str):
    config_file = src_dir / Path('run.conf')

    with config_file.open(mode="w") as cf:
        rev_str = f"revision_file={rev_file}"
        src_dir = f"src_dir={src_dir}"
        test_dir = f"test_dir={test_dir}"
        loc = "localizer=profile"
        target_file = f"bugged_file={manifest_files[0]}"
        cf.write(f"{rev_str}\n{src_dir}\n{test_dir}\nbuild_cmd={build_cmd}\ntest_cmd={test_cmd}\n{target_file}\n{loc}")

    return config_file


def write_revlog_file(work_dir: Path, neg_tests: int, pos_tests: int):
    rev_file = work_dir / "tests.revlog"

    with rev_file.open(mode="w") as rf:
        diff_cases = f"Diff Cases: Tot {neg_tests}"
        first_neg_test = pos_tests + neg_tests
        neg_tests = ' '.join([str(i) for i in range(pos_tests + 1, first_neg_test + 1)])
        pos_cases = f"Positive Cases: Tot {pos_tests}"
        pos_tests = ' '.join([str(i) for i in range(1, pos_tests + 1)])
        reg_cases = "Regression Cases: Tot 0"
        rf.write(f"-\n-\n{diff_cases}\n{neg_tests}\n{pos_cases}\n{pos_tests}\n{reg_cases}\n")

    return rev_file


class ProphetBuild(APIHandler):
    def __call__(self, signal: Signal, data: dict, *args, **kwargs):
        wrap_path, llvm_path = environ["PATH"].split(':')[:2]
        wrap_path = wrap_path.replace('/home/workspace/prophet', data['args']['dep_dir'])
        llvm_path = llvm_path.replace('/usr/local', data['args']['dep_dir'])

        data['args']['env'] = {
            'PATH': f"{wrap_path}:{llvm_path}",
            'COMPILE_CMD': environ["COMPILE_CMD"].replace("/usr/local", data['args']['dep_dir']),
            'INDEX_FILE': environ["INDEX_FILE"],
            'CC': 'gcc',
            'CXX': 'gcc'
        }

        response_json = super().__call__(signal.url, data)
        
        if isinstance(response_json, list):
            for r in response_json:
                exit_status = int(r.get('exit_status', 255))

                if exit_status != 0:
                    return False

            return True
        else:
            exit_status = int(response_json.get('exit_status', 255))

        return exit_status == 0


class ProphetTest(APIHandler):
    class Meta:
        label = 'test_api'

    def __call__(self, signal: Signal, data: dict, *args, **kwargs) -> bool:
        self.app.log.error(f"Test: {signal}")
        response_json = super().__call__(signal.url, data)
        # TODO: check if outputs should be written to __out
        # system("rm -rf __out")

        if isinstance(response_json, list):
            for r in response_json:
                exit_status = int(r.get('exit_status', 255))
                passed = r.get('passed', False)
                order = r.get('order', None)

                if name and passed and exit_status == 0:
                    print(order)

                if exit_status != 0:
                    return False

                if not passed:
                    return False

            return True
        else:
            exit_status = int(response_json.get('exit_status', 255))
            passed = response_json.get('passed', False)

        if not passed:
            return False

        return exit_status == 0


class Prophet(ToolHandler):
    """Prophet"""

    class Meta:
        label = 'prophet'
        version = ''

    def __init__(self, **kw):
        super().__init__(**kw)
        self._api_handlers = {
            'build': ProphetBuild,
            'test': ProphetTest
        }

    def repair(self, signals: dict, repair_request: RepairRequest) -> RepairCommand:
        work_dir = Path(repair_request.working_dir.parent / f"{repair_request.working_dir.name}_workdir")
        test_dir = repair_request.working_dir / 'tests'
#        work_dir.mkdir(exist_ok=True)
        build_file = write_sh_file(repair_request.working_dir, signals["build_cmd"], 'build.sh')
        test_file =  write_sh_file(repair_request.working_dir, signals["test_cmd"], 'test.sh')
        test_dir.mkdir(exist_ok=True)
        self.repair_cmd.add_arg(opt='-dump-passed-candidate', arg=str(work_dir / 'passed.txt'))
        self.repair_cmd.add_arg(opt='-r', arg=str(work_dir))
        rev_file = write_revlog_file(repair_request.working_dir, neg_tests=repair_request.args['neg_tests'],
                                     pos_tests=repair_request.args['pos_tests'])
        config_file = write_config_file(rev_file=rev_file, working_dir=work_dir, src_dir=repair_request.working_dir,
                                        test_dir=test_dir,
                                        manifest_files=list(repair_request.manifest.keys()),
                                        build_cmd=build_file, test_cmd=test_file)
        self.repair_cmd.add_arg(opt=str(config_file), arg='')

        return self.repair_cmd

    def get_patches(self, working_dir: str, target_files: List[str], **kwargs) -> Dict[str, Any]:
        # TODO: implement

        return {}

    def parse_extra(self, extra_args: List[str], signal: Signal) -> dict:
        """
            Parses extra arguments in the signals.
        """

        if signal.arg == 'build_cmd':
            opts, args = getopt.getopt(extra_args, "cd:hx")
            dryrun_src = ""

            for o, a in opts:
                if o == "-d":
                    dryrun_src = a

            if len(args) < 1:
                raise CommandError("Arguments must include: <directory> [-d src_file | -c] [-h]")

            if not path.exists(args[0]):
                raise CommandError("Directory does not exist!")

            return {
                'dryrun_src': args[1] if dryrun_src != "" else None,
                'out_dir': args[0]
            }

        else:
            if len(argv) < 4:
                raise CommandError("Arguments must include: <src_dir> <test_dir> <work_dir> [cases]")

            opts, args = getopt.getopt(extra_args, "p:")
            profile_dir = ""

            for o, a in opts:
                if o == "-p":
                    profile_dir = a

            return {
                'src_dir': args[0],
                'profile_dir': profile_dir,
                'cur_dir': args[0] if profile_dir == "" else profile_dir,
                'cases': args[3:] if len(args) > 3 else []
            }


def load(nexus):
    nexus.handler.register(Prophet)

import os

import shutil

from abc import abstractmethod
from typing import Any, ClassVar, Generator, List, Optional, Sequence, Tuple, Type
from typing import cast as typecast

from kat.harness import abstract_test, sanitize, variants, Name, Node, Test
from kat import manifests

AMBASSADOR_LOCAL = """
---
apiVersion: v1
kind: Service
metadata:
  name: {self.path.k8s}
spec:
  type: NodePort
  ports:
   - port: 80
  selector:
    service: {self.path.k8s}
---
apiVersion: v1
kind: Service
metadata:
  labels:
    service: {self.path.k8s}-admin
  name: {self.path.k8s}-admin
spec:
  type: NodePort
  ports:
  - name: {self.path.k8s}-admin
    port: 8877
    targetPort: 8877
  selector:
    service: {self.path.k8s}
---
apiVersion: rbac.authorization.k8s.io/v1beta1
kind: ClusterRole
metadata:
  name: {self.path.k8s}
rules:
- apiGroups: [""]
  resources:
  - services
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources:
  - configmaps
  verbs: ["create", "update", "patch", "get", "list", "watch"]
- apiGroups: [""]
  resources:
  - secrets
  verbs: ["get", "list", "watch"]
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {self.path.k8s}
---
apiVersion: rbac.authorization.k8s.io/v1beta1
kind: ClusterRoleBinding
metadata:
  name: {self.path.k8s}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: {self.path.k8s}
subjects:
- kind: ServiceAccount
  name: {self.path.k8s}
  namespace: default
---
apiVersion: v1
kind: Secret
metadata:
  name: {self.path.k8s}
  annotations:
    kubernetes.io/service-account.name: {self.path.k8s}
type: kubernetes.io/service-account-token
---
apiVersion: v1
kind: Secret
metadata:
  name: test-certs-secret
type: kubernetes.io/tls
data:
  tls.crt: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSURwakNDQW82Z0F3SUJBZ0lKQUpxa1Z4Y1RtQ1FITUEwR0NTcUdTSWIzRFFFQkN3VUFNR2d4Q3pBSkJnTlYKQkFZVEFsVlRNUXN3Q1FZRFZRUUlEQUpOUVRFUE1BMEdBMVVFQnd3R1FtOXpkRzl1TVJFd0R3WURWUVFLREFoRQpZWFJoZDJseVpURVVNQklHQTFVRUN3d0xSVzVuYVc1bFpYSnBibWN4RWpBUUJnTlZCQU1NQ1d4dlkyRnNhRzl6CmREQWVGdzB4T0RFd01UQXhNREk1TURKYUZ3MHlPREV3TURjeE1ESTVNREphTUdneEN6QUpCZ05WQkFZVEFsVlQKTVFzd0NRWURWUVFJREFKTlFURVBNQTBHQTFVRUJ3d0dRbTl6ZEc5dU1SRXdEd1lEVlFRS0RBaEVZWFJoZDJseQpaVEVVTUJJR0ExVUVDd3dMUlc1bmFXNWxaWEpwYm1jeEVqQVFCZ05WQkFNTUNXeHZZMkZzYUc5emREQ0NBU0l3CkRRWUpLb1pJaHZjTkFRRUJCUUFEZ2dFUEFEQ0NBUW9DZ2dFQkFMcTZtdS9FSzlQc1Q0YkR1WWg0aEZPVnZiblAKekV6MGpQcnVzdXcxT05MQk9jT2htbmNSTnE4c1FyTGxBZ3NicDBuTFZmQ1pSZHQ4UnlOcUFGeUJlR29XS3IvZAprQVEybVBucjBQRHlCTzk0UHo4VHdydDBtZEtEU1dGanNxMjlOYVJaT0JqdStLcGV6RytOZ3pLMk04M0ZtSldUCnFYdTI3ME9pOXlqb2VGQ3lPMjdwUkdvcktkQk9TcmIwd3ozdFdWUGk4NFZMdnFKRWprT0JVZjJYNVF3b25XWngKMktxVUJ6OUFSZVVUMzdwUVJZQkJMSUdvSnM4U042cjF4MSt1dTNLdTVxSkN1QmRlSHlJbHpKb2V0aEp2K3pTMgowN0pFc2ZKWkluMWNpdXhNNzNPbmVRTm1LUkpsL2NEb3BLemswSldRSnRSV1NnbktneFNYWkRrZjJMOENBd0VBCkFhTlRNRkV3SFFZRFZSME9CQllFRkJoQzdDeVRpNGFkSFVCd0wvTkZlRTZLdnFIRE1COEdBMVVkSXdRWU1CYUEKRkJoQzdDeVRpNGFkSFVCd0wvTkZlRTZLdnFIRE1BOEdBMVVkRXdFQi93UUZNQU1CQWY4d0RRWUpLb1pJaHZjTgpBUUVMQlFBRGdnRUJBSFJvb0xjcFdEa1IyMEhENEJ5d1BTUGRLV1hjWnN1U2tXYWZyekhoYUJ5MWJZcktIR1o1CmFodFF3L1gwQmRnMWtidlpZUDJSTzdGTFhBSlNTdXVJT0NHTFVwS0pkVHE1NDREUThNb1daWVZKbTc3UWxxam0KbHNIa2VlTlRNamFOVjdMd0MzalBkMERYelczbGVnWFRoYWpmZ2dtLzBJZXNGRzBVWjFEOTJHNURmc0hLekpSagpNSHZyVDNtVmJGZjkrSGJhRE4yT2g5VjIxUWhWSzF2M0F2dWNXczhUWCswZHZFZ1dtWHBRcndEd2pTMU04QkRYCldoWjVsZTZjVzhNYjhnZmRseG1JckpnQStuVVZzMU9EbkJKS1F3MUY4MVdkc25tWXdweVUrT2xVais4UGt1TVoKSU4rUlhQVnZMSWJ3czBmamJ4UXRzbTArZVBpRnN2d0NsUFk9Ci0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0K
  tls.key: LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUV2Z0lCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktnd2dnU2tBZ0VBQW9JQkFRQzZ1cHJ2eEN2VDdFK0cKdzdtSWVJUlRsYjI1ejh4TTlJejY3ckxzTlRqU3dUbkRvWnAzRVRhdkxFS3k1UUlMRzZkSnkxWHdtVVhiZkVjagphZ0JjZ1hocUZpcS8zWkFFTnBqNTY5RHc4Z1R2ZUQ4L0U4SzdkSm5TZzBsaFk3S3R2VFdrV1RnWTd2aXFYc3h2CmpZTXl0alBOeFppVms2bDd0dTlEb3ZjbzZIaFFzanR1NlVScUt5blFUa3EyOU1NOTdWbFQ0dk9GUzc2aVJJNUQKZ1ZIOWwrVU1LSjFtY2RpcWxBYy9RRVhsRTkrNlVFV0FRU3lCcUNiUEVqZXE5Y2RmcnJ0eXJ1YWlRcmdYWGg4aQpKY3lhSHJZU2IvczB0dE95UkxIeVdTSjlYSXJzVE85enAza0RaaWtTWmYzQTZLU3M1TkNWa0NiVVZrb0p5b01VCmwyUTVIOWkvQWdNQkFBRUNnZ0VBSVFsZzNpamNCRHViK21Eb2syK1hJZDZ0V1pHZE9NUlBxUm5RU0NCR2RHdEIKV0E1Z2NNNTMyVmhBV0x4UnR6dG1ScFVXR0dKVnpMWlpNN2ZPWm85MWlYZHdpcytkYWxGcWtWVWFlM2FtVHVQOApkS0YvWTRFR3Nnc09VWSs5RGlZYXRvQWVmN0xRQmZ5TnVQTFZrb1JQK0FrTXJQSWFHMHhMV3JFYmYzNVp3eFRuCnd5TTF3YVpQb1oxWjZFdmhHQkxNNzlXYmY2VFY0WXVzSTRNOEVQdU1GcWlYcDNlRmZ4L0tnNHhtYnZtN1JhYzcKOEJ3Z3pnVmljNXlSbkVXYjhpWUh5WGtyazNTL0VCYUNEMlQwUjM5VmlVM1I0VjBmMUtyV3NjRHowVmNiVWNhKwpzeVdyaVhKMHBnR1N0Q3FWK0dRYy9aNmJjOGt4VWpTTWxOUWtudVJRZ1FLQmdRRHpwM1ZaVmFzMTA3NThVT00rCnZUeTFNL0V6azg4cWhGb21kYVFiSFRlbStpeGpCNlg3RU9sRlkya3JwUkwvbURDSEpwR0MzYlJtUHNFaHVGSUwKRHhSQ2hUcEtTVmNsSytaaUNPaWE1ektTVUpxZnBOcW15RnNaQlhJNnRkNW9mWk42aFpJVTlJR2RUaGlYMjBONwppUW01UnZlSUx2UHVwMWZRMmRqd2F6Ykgvd0tCZ1FERU1MN21Mb2RqSjBNTXh6ZnM3MW1FNmZOUFhBMVY2ZEgrCllCVG4xS2txaHJpampRWmFNbXZ6dEZmL1F3Wkhmd3FKQUVuNGx2em5ncUNzZTMvUElZMy8zRERxd1p2NE1vdy8KRGdBeTBLQmpQYVJGNjhYT1B1d0VuSFN1UjhyZFg2UzI3TXQ2cEZIeFZ2YjlRRFJuSXc4a3grSFVreml4U0h5Ugo2NWxESklEdlFRS0JnUURpQTF3ZldoQlBCZk9VYlpQZUJydmhlaVVycXRob29BemYwQkJCOW9CQks1OHczVTloCjdQWDFuNWxYR3ZEY2x0ZXRCbUhEK3RQMFpCSFNyWit0RW5mQW5NVE5VK3E2V0ZhRWFhOGF3WXR2bmNWUWdTTXgKd25oK1pVYm9udnVJQWJSajJyTC9MUzl1TTVzc2dmKy9BQWM5RGs5ZXkrOEtXY0Jqd3pBeEU4TGxFUUtCZ0IzNwoxVEVZcTFoY0I4Tk1MeC9tOUtkN21kUG5IYUtqdVpSRzJ1c1RkVWNxajgxdklDbG95MWJUbVI5Si93dXVQczN4ClhWekF0cVlyTUtNcnZMekxSQWgyZm9OaVU1UDdKYlA5VDhwMFdBN1N2T2h5d0NobE5XeisvRlltWXJxeWcxbngKbHFlSHRYNU03REtJUFhvRndhcTlZYVk3V2M2K1pVdG4xbVNNajZnQkFvR0JBSTgwdU9iTkdhRndQTVYrUWhiZApBelkrSFNGQjBkWWZxRytzcTBmRVdIWTNHTXFmNFh0aVRqUEFjWlg3RmdtT3Q5Uit3TlFQK0dFNjZoV0JpKzBWCmVLV3prV0lXeS9sTVZCSW0zVWtlSlRCT3NudTFVaGhXbm5WVDhFeWhEY1FxcndPSGlhaUo3bFZSZmRoRWFyQysKSnpaU0czOHVZUVlyc0lITnRVZFgySmdPCi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS0K
"""

import base64, pytest, subprocess, sys, tempfile, time, yaml

def run(*args, **kwargs):
    for arg in "stdout", "stderr":
        if arg not in kwargs:
            kwargs[arg] = subprocess.PIPE
    return subprocess.run(args, **kwargs)

DEV = os.environ.get("AMBASSADOR_DEV", "0").lower() in ("1", "yes", "true")


@abstract_test
class AmbassadorTest(Test):

    """
    AmbassadorTest is a top level ambassador test.
    """

    OFFSET: ClassVar[int] = 0
    IMAGE_BUILT: ClassVar[bool] = False

    _index: Optional[int] = None
    _ambassador_id: Optional[str] = None
    name: Name
    path: Name

    def manifests(self) -> str:
        if DEV:
            return self.format(AMBASSADOR_LOCAL)
        else:
            return self.format(manifests.AMBASSADOR, image=os.environ["AMBASSADOR_DOCKER_IMAGE"])

    # Will tear this out of the harness shortly
    @property
    def ambassador_id(self) -> str:
        if self._ambassador_id is None:
            return self.name.k8s
        else:
            return typecast(str, self._ambassador_id)

    @ambassador_id.setter
    def ambassador_id(self, val: str) -> None:
        self._ambassador_id = val

    @property
    def index(self) -> int:
        if self._index is None:
            # lock here?
            self._index = AmbassadorTest.OFFSET
            AmbassadorTest.OFFSET += 1

        return typecast(int, self._index)

    def pre_query(self):
        if not DEV: return

        run("docker", "kill", self.path.k8s)
        run("docker", "rm", self.path.k8s)

        image = os.environ["AMBASSADOR_DOCKER_IMAGE"]

        if not AmbassadorTest.IMAGE_BUILT:
            AmbassadorTest.IMAGE_BUILT = True
            context = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            print("Starting docker build...", end="")
            sys.stdout.flush()
            result = run("docker", "build", context, "-t", image)
            try:
                result.check_returncode()
                print("done.")
            except Exception as e:
                print((result.stdout + b"\n" + result.stderr).decode("utf8"))
                pytest.exit("container failed to build")

        fname = "/tmp/k8s-%s.yaml" % self.path.k8s
        if os.path.exists(fname):
            with open(fname) as fd:
                content = fd.read()
        else:
            result = run("kubectl", "get", "-o", "yaml", "secret", self.path.k8s)
            result.check_returncode()
            with open(fname, "wb") as fd:
                fd.write(result.stdout)
            content = result.stdout
        secret = yaml.load(content)
        data = secret['data']
        # dir = tempfile.mkdtemp(prefix=self.path.k8s, suffix="secret")
        dir = "/tmp/%s-ambassadormixin-%s" % (self.path.k8s, 'secret')

        shutil.rmtree(dir, ignore_errors=True)
        os.mkdir(dir, 0o777)

        for k, v in data.items():
            with open(os.path.join(dir, k), "wb") as f:
                f.write(base64.decodebytes(bytes(v, "utf8")))
        print("Launching %s container." % self.path.k8s)
        result = run("docker", "run", "-d", "--name", self.path.k8s,
                     "-p", "%s:8877" % (8877 + self.index),
                     "-p", "%s:80" % (8080 + self.index),
                     "-p", "%s:443" % (8443 + self.index),
                     "-v", "%s:/var/run/secrets/kubernetes.io/serviceaccount" % dir,
                     "-e", "KUBERNETES_SERVICE_HOST=kubernetes",
                     "-e", "KUBERNETES_SERVICE_PORT=443",
                     "-e", "AMBASSADOR_ID=%s" % self.ambassador_id,
                     image)
        result.check_returncode()
        self.deadline = time.time() + 5

    def queries(self):
        if DEV:
            now = time.time()
            if now < self.deadline:
                time.sleep(self.deadline - now)
            result = run("docker", "ps", "-qf", "name=%s" % self.path.k8s)
            result.check_returncode()
            if not result.stdout.strip():
                result = run("docker", "logs", self.path.k8s, stderr=subprocess.STDOUT)
                result.check_returncode()
                print(result.stdout.decode("utf8"), end="")
                pytest.exit("container failed to start")
        return ()

    def scheme(self) -> str:
        return "http"

    def url(self, prefix) -> str:
        if DEV:
            port = 8443 if self.scheme() == 'https' else 8080
            return "%s://%s/%s" % (self.scheme(), "localhost:%s" % (port + self.index), prefix)
        else:
            return "%s://%s/%s" % (self.scheme(), self.path.k8s, prefix)

    def requirements(self):
        if not DEV:
            yield ("pod", "%s" % self.name.k8s)


@abstract_test
class ServiceType(Node):

    def config(self):
        if False: yield

    def manifests(self):
        return self.format(manifests.BACKEND)

    def requirements(self):
        yield ("pod", self.path.k8s)

class HTTP(ServiceType):
    pass

class GRPC(ServiceType):
    pass


@abstract_test
class MappingTest(Test):

    target: ServiceType
    options: Sequence['OptionTest']

    def init(self, target: ServiceType, options = ()) -> None:
        self.target = target
        self.options = list(options)


@abstract_test
class OptionTest(Test):

    VALUES: ClassVar[Any] = None

    @classmethod
    def variants(cls):
        if cls.VALUES is None:
            yield cls()
        else:
            for val in cls.VALUES:
                yield cls(val, name=sanitize(val))

    def init(self, value = None):
        self.value = value

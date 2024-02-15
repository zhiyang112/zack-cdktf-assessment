import pytest
from cdktf import Testing
from src.backend import BackendStack
from src.frontend import FrontEndStack
from cdktf import TerraformStack

# The tests below are example tests, you can find more information at
# https://cdk.tf/testing


class TestMain:
    def test_my_app(self):
        assert True

    # def test_should_contain_resource(self):
    #     stack = TerraformStack(Testing.app(), "stack")
    #     BackendStack(stack, "iac-assignment-backend")
    #     # synthesized = Testing.synth(stack)
    #     # print(synthesized)

    #     assert Testing.to_have_provider(self, "aws")

    # def test_should_use_an_ubuntu_image(self):
    #    assert Testing.to_have_resource_with_properties(self.synthesized, Image.TF_RESOURCE_TYPE, {
    #        "name": "ubuntu:latest",
    #    })

    def test_check_validity(self):
        stack = TerraformStack(Testing.app(), "stack")
        backend_stack = BackendStack(stack, "iac-assignment-backend")
        front_end = FrontEndStack(stack, "iac-assignment-frontend")

        assert Testing.to_be_valid_terraform(Testing.full_synth(backend_stack))
        assert Testing.to_be_valid_terraform(Testing.full_synth(front_end))

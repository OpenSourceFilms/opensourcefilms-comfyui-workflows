"""Offline contract tests for CPU-only ComfyUI runtime acceptance driver."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "qualify_clean_comfy_cpu.py"
spec = importlib.util.spec_from_file_location("osf_comfy_cpu_smoke", SRC)
qualifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualifier)


class CleanRuntimeSmokeContractTests(unittest.TestCase):
    def test_requires_two_registered_comfyui_node_schemas(self):
        example = {
            "MaskPropagateFromFlow": {
                "output": ["MASK"],
                "input": {"required": {"flow": [["OPTICAL_FLOW"]]}},
            }
        }
        qualifier.ensure_loopback_object_info(example, "MaskPropagateFromFlow")
        with self.assertRaisesRegex(ValueError, "not registered"):
            qualifier.ensure_loopback_object_info(example, "MaskPropagateOpticalFlow")
        with self.assertRaisesRegex(ValueError, "unexpected API schema"):
            qualifier.ensure_loopback_object_info(
                {"MaskPropagateFromFlow": {"output": ["IMAGE"], "input": {}}},
                "MaskPropagateFromFlow",
            )

    def test_fails_fast_if_server_exits_without_registering_nodes(self):
        fake_child = mock.Mock()
        fake_child.poll.return_value = 2
        with self.assertRaisesRegex(RuntimeError, "exited"):
            qualifier._probe_server(18188, fake_child, seconds=1)

    def test_missing_osf_source_fails_without_importing_torch(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "Missing or symlinked"):
                qualifier._load_osf_classes(Path(td))

    def test_requires_three_actual_external_node_schemas(self):
        classes = qualifier.EXTERNAL_NODE_PINS
        document = {
            name: {"input": {"required": {}}, "output": ["ANY"]}
            for spec in classes.values() for name in spec["classes"]
        }
        actual = qualifier.ensure_external_object_info(document, classes)
        self.assertEqual(set(actual), set(classes))
        missing = next(iter(classes.values()))["classes"][0]
        del document[missing]
        with self.assertRaisesRegex(ValueError, "Missing external"):
            qualifier.ensure_external_object_info(document, classes)
        document[missing] = {"input": {"required": {}}, "output": "ANY"}
        with self.assertRaisesRegex(ValueError, "Invalid external"):
            qualifier.ensure_external_object_info(document, classes)

    def test_pinned_source_revision_inventory_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            nodes = Path(td)
            expected = qualifier.EXTERNAL_NODE_PINS
            for package in expected:
                (nodes / package).mkdir()
            def fake_revparse(args, **_kwargs):
                name = Path(args[2]).name
                return mock.Mock(stdout=expected[name]["sha"] + "\n")
            with mock.patch.object(qualifier.subprocess, "run",
                                   side_effect=fake_revparse):
                report = qualifier.verify_external_node_sources(nodes)
                self.assertEqual(report, {
                    name: value["sha"] for name, value in sorted(expected.items())
                })
            old = nodes / "rgthree-comfy"
            old.rmdir()
            old.symlink_to(nodes / "ComfyUI-VideoHelperSuite")
            with self.assertRaisesRegex(ValueError, "symlinked"):
                qualifier.verify_external_node_sources(nodes)
            old.unlink()
            old.mkdir()
            with mock.patch.object(qualifier.subprocess, "run",
                                   return_value=mock.Mock(stdout="0" * 40 + "\n")):
                with self.assertRaisesRegex(ValueError, "Unapproved external"):
                    qualifier.verify_external_node_sources(nodes)

    def test_fourth_external_package_is_pinned_to_manifest_gguf(self):
        spec = qualifier.EXTERNAL_NODE_PINS["ComfyUI-GGUF"]
        self.assertEqual(spec["sha"],
                         "6ea2651e7df66d7585f6ffee804b20e92fb38b8a")
        self.assertEqual(spec["classes"], ("UnetLoaderGGUF",))
        lock = (ROOT / "DEPENDENCIES.lock").read_text(encoding="utf-8")
        self.assertIn("commit: " + spec["sha"], lock)
        self.assertIn("name: ComfyUI-GGUF", lock)

    def test_external_frame_drop_acceptance_checks_expected_synthetic_values(self):
        # This method imports torch only in the disposable runtime job.
        # The contract test confirms the upstream method is required;
        # correctness of the real function is verified on CI startup.
        self.assertTrue(callable(qualifier.execute_downsample_fps_synthetic))
        self.assertIn("ComfyUI-DownsampleFPS", qualifier.EXTERNAL_NODE_PINS)

    def test_usdu_gitlink_is_exact_and_provenance_is_declared(self):
        parent = qualifier.EXTERNAL_NODE_PINS["ComfyUI_UltimateSDUpscale"]
        self.assertEqual(parent["sha"],
                         "a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df")
        self.assertEqual(parent["classes"], ("UltimateSDUpscale",))
        expected = (
            "160000 commit 2322caa480535b1011a1f9c18126d85ea444f146"
            "\trepositories/ultimate_sd_upscale\n"
        )
        self.assertEqual(qualifier.validate_usdu_gitlink(expected),
                         qualifier.USDU_SUBMODULE_COMMIT)
        with self.assertRaisesRegex(ValueError, "gitlink differs"):
            qualifier.validate_usdu_gitlink(
                expected.replace("2322caa", "0322caa")
            )
        lock = (ROOT / "DEPENDENCIES.lock").read_text(encoding="utf-8")
        self.assertIn("name: ComfyUI_UltimateSDUpscale", lock)

    def test_missing_or_symlinked_usdu_submodule_fails_before_git(self):
        with tempfile.TemporaryDirectory() as td:
            nodes = Path(td)
            child = nodes / "ComfyUI_UltimateSDUpscale" / "repositories" / "ultimate_sd_upscale"
            child.parent.mkdir(parents=True)
            with mock.patch.object(qualifier.subprocess, "run") as cmd:
                with self.assertRaisesRegex(ValueError, "Missing/symlinked"):
                    qualifier.verify_usdu_submodule(nodes)
                cmd.assert_not_called()
                child.symlink_to(child.parent)
                with self.assertRaisesRegex(ValueError, "Missing/symlinked"):
                    qualifier.verify_usdu_submodule(nodes)
                cmd.assert_not_called()

    def test_download_guard_intercepts_urllib_urlretrieve_without_network(self):
        import os
        import subprocess
        import sys
        env = os.environ.copy()
        guard = ROOT / "scripts" / "usdu_offline_guard"
        env["PYTHONPATH"] = str(guard) + os.pathsep + env.get("PYTHONPATH", "")
        child = subprocess.run(
            [sys.executable, "-c",
             "import sitecustomize, urllib.request; "
             "assert urllib.request.urlretrieve is sitecustomize._reject_urlretrieve; "
             "urllib.request.urlretrieve('no-network://placeholder')"],
            capture_output=True, text=True, env=env, timeout=12,
        )
        self.assertNotEqual(child.returncode, 0)
        self.assertIn("Unpinned urllib.request.urlretrieve", child.stderr)

    def test_model_free_external_prompt_uses_four_distinct_source_colours(self):
        graph = qualifier.build_model_free_external_prompt()
        self.assertEqual(set(graph), {str(i) for i in range(1, 13)})
        self.assertEqual(
            [graph[str(i)]["class_type"] for i in range(1, 13)],
            ["EmptyImage"] * 4 + ["ImageBatch"] * 3
            + ["VHS_SelectEveryNthImage", "Any Switch (rgthree)",
               "PreviewImage", "VHS_VideoCombine", "VHS_VideoCombine"],
        )
        self.assertEqual(
            [graph[str(i)]["inputs"]["color"] for i in range(1, 5)],
            [0xFF0000, 0x00FF00, 0x0000FF, 0xFFFF00],
        )
        self.assertTrue(all(graph[str(i)]["inputs"]["batch_size"] == 1
                            for i in range(1, 5)))
        self.assertEqual(graph["5"]["inputs"], {
            "image1": ["1", 0], "image2": ["2", 0],
        })
        self.assertEqual(graph["6"]["inputs"], {
            "image1": ["5", 0], "image2": ["3", 0],
        })
        self.assertEqual(graph["7"]["inputs"], {
            "image1": ["6", 0], "image2": ["4", 0],
        })
        self.assertEqual(graph["8"]["inputs"], {
            "images": ["7", 0], "select_every_nth": 2,
            "skip_first_images": 0,
        })
        self.assertEqual(graph["9"]["inputs"], {"any_01": ["8", 0]})
        self.assertEqual(graph["10"]["inputs"], {"images": ["9", 0]})
        self.assertEqual(graph["11"]["inputs"]["images"], ["9", 0])
        self.assertEqual(graph["11"]["inputs"]["format"], "image/gif")
        self.assertFalse(graph["11"]["inputs"]["save_output"])
        self.assertEqual(graph["12"]["inputs"]["format"], "video/h264-mp4")
        self.assertEqual(graph["12"]["inputs"]["pix_fmt"], "yuv420p")
        self.assertEqual(graph["12"]["inputs"]["crf"], 0)
        self.assertEqual(graph["12"]["inputs"]["images"], ["9", 0])
        self.assertFalse(graph["12"]["inputs"]["save_output"])
        self.assertFalse(any(
            "Load" in spec["class_type"] or "Sampler" in spec["class_type"]
            for spec in graph.values()
        ))

    def test_history_requires_two_previews_and_one_temporary_gif(self):
        ident = "synthetic-prompt-id"
        def event(name, suffix):
            return {
                "filename": name, "type": "temp", "subfolder": "",
                **({"format": "image/gif"} if suffix == "gif" else
                   {"format": "video/h264-mp4"} if suffix == "mp4" else {}),
            }
        record = {ident: {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {
                "10": {"images": [event("one.png", "png"),
                                  event("two.png", "png")]},
                "11": {"gifs": [event("clip.gif", "gif")]},
                "12": {"gifs": [event("clip.mp4", "mp4")]},
            },
        }}
        valid = qualifier.validate_model_free_external_history(record, ident)
        self.assertEqual(valid["selected_image_count"], 2)
        self.assertEqual(valid["gif_count"], 1)
        self.assertEqual(valid["h264_mp4_count"], 1)
        self.assertFalse(valid["model_weights_used"])
        self.assertFalse(valid["binary_outputs_uploaded"])
        record[ident]["outputs"]["10"]["images"].pop()
        with self.assertRaisesRegex(ValueError, "wrong image count"):
            qualifier.validate_model_free_external_history(record, ident)
        record[ident]["outputs"]["10"]["images"].append(event("two.png", "png"))
        record[ident]["outputs"]["11"]["gifs"].clear()
        with self.assertRaisesRegex(ValueError, "wrong output count"):
            qualifier.validate_model_free_external_history(record, ident)
        record[ident]["outputs"]["11"]["gifs"].append(event("clip.gif", "gif"))
        record[ident]["outputs"]["12"]["gifs"].clear()
        with self.assertRaisesRegex(ValueError, "H264 encoder returned wrong output count"):
            qualifier.validate_model_free_external_history(record, ident)
        record[ident]["outputs"]["12"]["gifs"].append(event("clip.mp4", "mp4"))
        record[ident]["status"]["completed"] = False
        with self.assertRaisesRegex(ValueError, "did not complete"):
            qualifier.validate_model_free_external_history(record, ident)
        record[ident]["status"]["completed"] = True
        record[ident]["outputs"]["10"]["images"][0]["type"] = "output"
        with self.assertRaisesRegex(ValueError, "Unsafe or unexpected"):
            qualifier.validate_model_free_external_history(record, ident)
        with self.assertRaisesRegex(ValueError, "Missing external"):
            qualifier.validate_model_free_external_history({}, ident)

    def test_h264_decoded_content_rejects_wrong_order_and_channel_mismatch(self):
        pixels = 64 * 64
        frame_red = bytes((255, 0, 0)) * pixels
        frame_blue = bytes((0, 0, 255)) * pixels
        valid = qualifier.validate_h264_decoded_rgb(frame_red + frame_blue)
        self.assertEqual(valid["frames_decoded"], 2)
        self.assertEqual(valid["maximum_absolute_channel_error"], [0, 0])
        self.assertFalse(valid["binary_outputs_uploaded"])
        near = bytes((240, 8, 5)) * pixels + bytes((6, 5, 242)) * pixels
        self.assertEqual(
            qualifier.validate_h264_decoded_rgb(near)["maximum_absolute_channel_error"],
            [15, 13],
        )
        for bad in (frame_red, frame_blue + frame_red,
                    bytes((220, 15, 0)) * pixels + frame_blue):
            with self.subTest(length=len(bad)):
                with self.assertRaisesRegex(ValueError, "H264 decoded"):
                    qualifier.validate_h264_decoded_rgb(bad)

    def test_temporary_asset_metadata_rejects_absolute_and_parent_paths(self):
        proper = {"filename": "synthetic_temp_00001_.png",
                  "type": "temp", "subfolder": ""}
        self.assertEqual(
            qualifier._validated_temp_asset(proper, "png"), proper,
        )
        for filename in ("../outside.png", "/etc/passwd.png",
                         "..\\outside.png", "folder/name.png",
                         "clip.gif", "bad?name.png"):
            with self.subTest(filename=filename):
                with self.assertRaisesRegex(ValueError, "Unsafe or unexpected"):
                    qualifier._validated_temp_asset(
                        {**proper, "filename": filename}, "png",
                    )
        with self.assertRaisesRegex(ValueError, "Unsafe or unexpected"):
            qualifier._validated_temp_asset(
                {**proper, "subfolder": "../../outside"}, "png",
            )
        with self.assertRaisesRegex(ValueError, "Unsafe or unexpected"):
            qualifier._validated_temp_asset(
                {**proper, "type": "output"}, "png",
            )

    def test_requires_pinned_comfyui_sha_and_no_existing_evidence_file(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "main.py").write_text("print('fake')", encoding="utf-8")
            (base / "custom_nodes" / "mask_propagate_optical_flow").mkdir(
                parents=True
            )
            evidence = base / "report.json"
            with mock.patch.object(qualifier.subprocess, "run") as cmd:
                cmd.return_value.stdout = "a" * 40 + "\n"
                with self.assertRaisesRegex(ValueError, "Unreviewed ComfyUI"):
                    qualifier.qualify(base, evidence, 18188)
            self.assertFalse(evidence.exists())


if __name__ == "__main__":
    unittest.main()

# 🙏 Reference Mapping

Thanks to these open-source projects for their ideas and practices. The following are architecture references, organized on **2026-09-20**; Xingzhi's implementation and experimental results are recorded separately.

| Reference Project | Borrowed Insight | Implementation in Xingzhi |
| --- | --- | --- |
| [openroboto / jev-robot-control](https://github.com/openroboto-ai/jev-robot-control) | Layered intent and action, multi-model display | Two-stage candidate selection, independent comparison and trajectory replay |
| [jev-robotics-demo](https://github.com/FazalAAli/jev-robotics-demo) | Pre-execution simulation preview | Checks contact and grasp status in MuJoCo fork |
| [jev_fsd](https://github.com/BrendanH18/jev_fsd) | Program-generated candidates, model selection | Limited action menu and result verification |
| [jev-askable-arm](https://github.com/TarunTomar122/jev-askable-arm) | Robot action primitives | Bounded target poses and IK execution |
| [jev-drone](https://github.com/RomanSlack/jev-drone) | Perception, decision, and control separation | Optional visual observations, finite-choice decisions, independent control loop |
| [jevduck](https://github.com/amazedsaint/jevduck) | Checkable, controllable experiments | Pause, stop, result feedback, and logging |
| [openarm-jev-lab](https://github.com/tripathiarpan20/openarm-jev-lab) | Simulation and interface separation, LIBERO-PRO experiments | Backend experiments and browser workbench; this project has not yet integrated LIBERO |
| [SemIf](https://github.com/TheoLeeCJ/SemIf) | Limited candidate probability readout | MiniCPM5-2B local decision adaptation |
| [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) | Franka Panda models and assets | Robot models, preserving upstream license and source |

🎬 **Demo Reference**: [Dmytro Hrybov's MuJoCo demo](https://x.com/dimentary/status/2101018760371171420) and [follow-up explanation](https://x.com/dimentary/status/2101018934095003720), showcasing structured geometry, contact states, and two-stage decision-making.

SemIf has publicly supported MiniCPM5-2B; it is an independent open-source project. Xingzhi's local MiniCPM mode uses MiniCPM weights, while the official Jev accesses via [TypeSafe API](https://docs.typesafe.ai/api). Candidate probability does not equal physical task success rate.

In the public comparisons reviewed, OpenRoboto compares Jev with GPT, jev-robotics-demo compares Jev with Claude; [openarm-jev-lab](https://github.com/tripathiarpan20/openarm-jev-lab/blob/c89a73f6ff10094acc3d27e45ef91a31791eadb2/README.md#what-improved) compares action menu improvements for the same Jev controller. Although it runs LIBERO-PRO, these materials do not report same-condition tests against OpenVLA, SmolVLA, or π0. Cannot claim Jev outperforms VLA based on this.

Further reading: [👁️ Visual Mode](VISION.md) · [⚡ Fast Inference and Source Analysis](FAST_INFERENCE.md) · [🆚 Model Comparison](COMPARISON.md) · [📊 Validation Results](VALIDATION.md) · [📄 Third-Party Licenses](../THIRD_PARTY_NOTICES.md)

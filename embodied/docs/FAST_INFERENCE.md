# Jev Fast Reasoning and Open Source Implementation

The speed of the Jev robotic arm demonstration comes from state organization, limited candidate selection, merge request, and continuous motion control. The model typically makes decisions between actions, while the physics engine and visuals update at their respective frequencies.

The following information was checked on **2026-09-20**. TypeSafe Jev is served through an API; the robot integration projects referenced here are open source, but Jev weights have not been released.

## Official Interface

Jev receives `state + questions`, returns `answers`. The program provides candidates, the model outputs selection and probability, eliminating lengthy text generation.

| Capability | Documentation Description | Use in Robotic Arm |
| --- | --- | --- |
| `Choice` | Select from given candidates, return probability for each item | Selection phase, movement direction, gripper command |
| `Noul` | Return probability for yes/no questions | Semantic condition judgment, precise contact still detected by code |
| `Score` | Rate within described levels | Express preference, precise distance still calculated by code |
| Multi-question request | Read once into the same state, evaluate each question in parallel | Ask independent questions such as XYZ and gripper at once |

Officially, the training method is called RLCD, with goals including structured decision-making and probability calibration. The public interface does not provide enough information to confirm network structure, parameter scale, or reasoning kernel. Probability calibration describes statistical behavior across multiple predictions and does not guarantee correctness of a single action.

Source: [System One](https://docs.typesafe.ai/concepts/system-one), [API](https://docs.typesafe.ai/api), [Model and State Reuse](https://docs.typesafe.ai/models), [Training Objective](https://docs.typesafe.ai/introduction/machine-learning-primer).

## How to Use the Open Source Robotic Arm Project

### First select intent, then merge action questions

[openroboto-ai/jev-robot-control](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/incremental_policy.py) First request `intent`, then write the selected intent into the state; the second request simultaneously asks **X, Y, Z, gripper**. The two stages are dependent and still require serial execution; merging the four action channels eliminates sequential requests per axis.

Its Jev branch calls the OpenRouter experimental decisions interface, using model `typesafe/jev-1.13`. The regular language model takes another branch. When using this set of addresses, OpenRouter corresponding permissions are required and cannot be entered into the TypeSafe official entrance.

### Code calculation, preview, model selection

[FazalAAli/jev-robotics-demo](https://github.com/FazalAAli/jev-robotics-demo/blob/531de61a75f386b0847f5f6f809a11424a75c29b/jev_agent.py) First calculate distance and direction, propose small actions, simulate in MuJoCo replica; after filtering unreachable, collidable, or falling actions, write prediction results into candidate description. Only one valid candidate leads to direct execution.

After reaching waypoints, it also merges "next target", "whether completed", and optional "grab/release" questions. Source code separately accumulates model wait, preview, and execution time, facilitating determination of which part is slowest. State extraction, candidate generation, collision check, and motion control are all handled by code.

### Visual frequency and model frequency are separate

openroboto's [physical loop](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/incremental_env.py) step size is `0.002 s`, approximately one frame per 16 steps, i.e., 500 simulation steps per second and 31.25 frames. [Run script](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/incremental_run.py) sequentially requests intent and action per round and then executes. The actual runtime of the entire simulation also includes model waiting time and cannot be derived from frame rate to estimate inference speed.

Xingzhi also uses this division of labor. When comparing, need to separately look at model duration, number of calls, simulation time, and actual total runtime of the whole simulation.

## How the three-column demo plays

openroboto's "Same task. Different decisions." page simultaneously displays Jev 1.13, GPT-6 Astra, and GPT-4.1 mini, and marks **RECORDED EXECUTION**. During verification, the repository `main` is the fixed `7a4ed8b` mentioned above.

[Three-column server](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/incremental_triple_app.py) reads existing JSON, images, and MP4; [frontend](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/incremental_triple.html) plays back using the same simulation time axis. Clicking Play does not initiate model requests, and playback also skips API waits. The wall time on the page comes from the full run record, including these waits.

Its [result description](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/docs/RESULTS.md) lists:

| Controller | Simulation time | Actual runtime, including API waits | This result |
| --- | --- | --- | --- |
| Jev 1.13 | 36.16 seconds | 181.847 seconds | Placement successful |
| GPT-6 Astra | 33.92 seconds | 707.274 seconds | Placement successful |
| GPT-4.1 mini | 51.20 seconds | 704.253 seconds | Reached 160 round limit |

[Data list](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/incremental_triple_data.py) shows that Jev and GPT-6 come from `20260919-200239-715974-0`, while mini comes from an earlier `20260919-193012-198478-0`. The loader checks the same initial observation, physical source code hash, seed 0 and 160 round limit, and records file source and hash. Action options and commands are the same, but parameters and timeouts differ: mini uses 35-second HTTP timeout, newer pairs use 90 seconds. Each model has only one seed-0 record, which is insufficient to compare general success rate.

The repository can also run real experiments: [dual-model pairing script](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/incremental_pair.py) uses two worker threads to call concurrently, [reproduce command](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/reproduce.py) with `--controller all` runs the three groups sequentially. They are different entry points from just reading playback.

Xingzhi borrowed and displayed side-by-side, but separates real-time operation and playback with labels. Also need to note that the Jev probability in the original demo comes from the interface, while the values for the two GPTs come from model-generated JSON, and their meanings are not the same. The above conclusions are based on public source code and records; this machine did not rerun the project's model experiments or trajectory verifier.

## How MiniCPM directly scores candidates

Local path reference [SemIf direct.py](https://github.com/TheoLeeCJ/SemIf/blob/ca3ba65f142967030ecb453346e94d6f476a69df/src/semif_phase1/direct.py):

```text
Status + Question + A/B/C Candidate
          ↓ One forward pass
Read the value at the last position corresponding to A/B/C of logits
          ↓ across candidates softmax
Obtain scores and select
```

Xingzhi only projects the output weights corresponding to candidate letters, reducing the output computation of the full vocabulary, and checks that letters are indeed single tokens at the boundaries of the full prompt. The entire input still needs to pass through the model, and long state and repeated history will still increase latency.

This method yields relative scores among candidates, which have not yet been calibrated on our robotic arm tasks. It uses MiniCPM weights, with training methods and server implementations differing from the official Jev. The interface displays candidate scores and selection, but does not show hidden reasoning processes.

## Real-world testing and input optimization on M2

The early baseline for this project submission [`72beb40`](https://github.com/FBddcz/embodied-jev/tree/72beb407d17fa1c0d072ad472ddc258717a1a628), hint version `phase-conditions-v2`. At that time, each round could call the model at most twice, sending the full observation and the last three full results, using `use_cache=False`, with no reuse of cross-question prefixes.

M2 / 16 GB, Torch 2.6.0, Transformers 4.57.6 FP16 development experiment, loading once with warm-up takes about **18.75–29.35 seconds**, single decision with threshold 0 takes about **1.13–5.57 seconds**. Background load is not fixed, these numbers only describe the running at that time. Full data see [validation record](VALIDATION.md) and [measurement summary](results/minicpm-fp16-2026-09-20.json).

The current preset skill implementation includes two optimizations:

- Input changed to compact geometry, contact relationships, and results of the last two actions; v4 adds displacement and gripper command from actual staged planning.
- HTTP adapter uses `httpx.Client` to reuse connections and logs calls and latency of failed requests.

Tight input experiments remain **0/3 successful**, the model repeatedly approaches without completing the grasp. Shorter runtime after reducing input or stopping early cannot serve as a conclusion for control quality or overall acceleration. HTTP connection reuse can reduce handshake overhead, but server-side computation, queuing, and network still require real-world testing, see [HTTPX documentation](https://www.python-httpx.org/advanced/clients/).

## Next directions worth testing

### State and Candidate Description

Precise geometric calculations are delegated to code, with the model retaining position, relative displacement, alignment relationships, gripper, and contact facts, and specifying units and thresholds. Historical focus records "what was executed" and "what changes occurred". Test candidate order changes to avoid selection based solely on prior positioning.

This also aligns with the recommendation in [Jev 1.13 Known Limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13): let code perform arithmetic, filter irrelevant state, and reduce complex indirect reasoning.

### Merge independent questions under the same state

When selecting the action-dependency stage, you must first choose the stage; you can also pre-prepare action questions for each stage, and after receiving the results, use the selected stage's answer. The official term for the latter method is [speculative fan-out](https://docs.typesafe.ai/patterns/fan-out), which requires simultaneously comparing additional tokens, preview costs, and latency.

Official independent evaluation for each question; the question name will not be passed to the model, and its meaning must be written in `instructions` and the candidate description. The standard chat API returns JSON, which does not mean it uses the same parallel evaluation mechanism.

### Prefix Cache and Quantization

[SemIf shared.py](https://github.com/TheoLeeCJ/SemIf/blob/ca3ba65f142967030ecb453346e94d6f476a69df/src/semif_phase1/shared.py) First calculate the KV prefix of the same state, then copy the cache and process the problem suffix in parallel, while checking the complete token prefix, suffix position, and padding. After the robot moves, the state has changed and only the prefix confirmed unchanged can be reused; the cache will also occupy additional memory. Enabling `use_cache` separately without reusing the return value will not bring cross-request benefits.

MiniCPM official provides [MLX](https://huggingface.co/openbmb/MiniCPM5-2B-MLX) and [GGUF](https://huggingface.co/openbmb/MiniCPM5-2B-GGUF) quantized weights. After integration, it needs to be compared with FP16 on candidate probabilities, action selection, latency, and overall success rate; speed numbers should come from the same model and device.

## How to record speed test

First conduct a short test on the fixed state, then run the full task. Suggest recording:

- Code, prompt, actual model version, weight revision, precision, device, and inference library version.
- Complete state, question, candidate, input token count, and single-stage/two-stage/merged request settings.
- Cold start, single selection, round decision, preview, execution, and total runtime; report sample count, median, P95, retain failures and timeouts.
- GPU synchronization and timing boundary; MLX requires explicit evaluation, API end-to-end time includes network.
- Legal output rate, task success rate, repeated actions, stop reason, call count and token; cost calculated based on actual billing.

In the official [13 example questions](https://docs.typesafe.ai/cookbooks/parallel_questions), the merge request takes about **0.27 seconds**, and 13 serial requests take **2.71 seconds**. It uses `jev-1.12`, processes a GDPR document of about 54,000 characters, and repeats each method 5 times. This is an example of multi-question merging and cannot be directly applied to robotic arms or local MiniCPM speed; if serial requests are changed to client concurrency, the comparison results will also change.

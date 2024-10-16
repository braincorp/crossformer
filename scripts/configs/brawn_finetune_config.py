"""Configuration for finetuning on Brawn datasets."""
import os

from ml_collections import ConfigDict
from ml_collections.config_dict import FieldReference, placeholder

from crossformer.utils.spec import ModuleSpec


def get_config():
    brawn_artifacts_directory = os.path.expanduser("~/brawn_artifacts")
    if not os.path.exists(brawn_artifacts_directory):
        os.makedirs(brawn_artifacts_directory)

    checkpoints_directory = os.path.expanduser("~/brawn_artifacts/checkpoints")
    if not os.path.exists(checkpoints_directory):
        os.makedirs(checkpoints_directory)

    # whether to finetune the entire model or just the action head
    mode = "full"

    # whether to finetune with image conditioning, language conditioning, or both
    task = "language_conditioned"

    # the name of the action head to finetune
    head_name = "single_arm"

    assert task in ["image_conditioned", "language_conditioned", "multimodal"]
    assert mode in ["full", "head_only"]

    # fill this in to configure data loading for your dataset.
    FINETUNING_KWARGS = dict(
        name="episodes_pick_bottled_sugar_lab_first_60_openvla_rlds",
        data_dir=os.path.expanduser("~/brawn_artifacts/datasets/dobot_nova5/episodes_pick_bottled_sugar_lab"),
        image_obs_keys={"primary": "static_rgb_image"},
        proprio_obs_keys={},
        language_key="language_instruction",
        action_proprio_normalization_type="normal",
        # We want to avoid normalizing the gripper
        action_normalization_mask=[True, True, True, True, True, True, False],
        # standardize_fn is dynamically loaded from a file
        standardize_fn=ModuleSpec.create(
            "crossformer.data.oxe.oxe_standardization_transforms:brawn_dataset_transform",
        ),
    )

    if mode == "full":
        frozen_keys = None
    elif mode == "head_only":
        frozen_keys = ("crossformer_transformer.*",)
    else:
        raise ValueError("Invalid mode")

    max_steps = FieldReference(100000)
    window_size = FieldReference(default=1)

    config = dict(
        # update_config=UPDATE_CONFIG, # uncomment this line to add new observation tokenizer and action head
        pretrained_path="hf://rail-berkeley/crossformer",
        pretrained_step=placeholder(int),
        batch_size=128,
        shuffle_buffer_size=10000,
        num_steps=max_steps,
        log_interval=100,
        eval_interval=1000,
        save_interval=1000,
        save_dir=checkpoints_directory,
        seed=42,
        wandb=dict(
            project="crossformer-fine-tuning",
            group=placeholder(str),
            entity="research-development",
        ),
        dataset_kwargs=FINETUNING_KWARGS,
        modality=task,
        finetuning_mode=mode,
        head_name=head_name,
        window_size=window_size,
        optimizer=dict(
            learning_rate=dict(
                name="cosine",
                init_value=0.0,
                peak_value=3e-4,
                warmup_steps=2000,
                decay_steps=max_steps,
                end_value=0.0,
            ),
            weight_decay=0.01,
            clip_gradient=1.0,
            frozen_keys=frozen_keys,
            grad_accumulation_steps=2,  # if you are using grad accumulation, you need to adjust max_steps accordingly
        ),
        val_kwargs=dict(
            val_shuffle_buffer_size=1000,
            num_val_batches=16,
        ),
    )

    if task == "image_conditioned":
        goal_relabeling_strategy = "uniform"
        keep_image_prob = 1.0
    elif task == "language_conditioned":
        goal_relabeling_strategy = None
        keep_image_prob = 0.0
    elif task == "multimodal":
        goal_relabeling_strategy = "uniform"
        keep_image_prob = 0.5
    else:
        raise ValueError("Invalid modality")

    traj_transform_kwargs = dict(
        window_size=window_size,
        action_horizon=4,
        goal_relabeling_strategy=goal_relabeling_strategy,
        task_augment_strategy="delete_task_conditioning",
        task_augment_kwargs=dict(
            keep_image_prob=keep_image_prob,
        ),
    )
    workspace_augment_kwargs = dict(
        random_resized_crop=dict(scale=[0.8, 1.0], ratio=[0.9, 1.1]),
        random_brightness=[0.1],
        random_contrast=[0.9, 1.1],
        random_saturation=[0.9, 1.1],
        random_hue=[0.05],
        augment_order=[
            "random_resized_crop",
            "random_brightness",
            "random_contrast",
            "random_saturation",
            "random_hue",
        ],
    )

    frame_transform_kwargs = dict(
        resize_size={
            "primary": (224, 224),  # workspace (3rd person) camera is at 224x224
        },
        image_augment_kwargs=dict(
            primary=workspace_augment_kwargs,
        ),
    )
    # If the default data loading speed is too slow, try these:
    config[
        "frame_transform_threads"
    ] = 16  # for the most CPU-intensive ops (decoding, resizing, augmenting)

    config["traj_transform_kwargs"] = traj_transform_kwargs
    config["frame_transform_kwargs"] = frame_transform_kwargs
    return ConfigDict(config)

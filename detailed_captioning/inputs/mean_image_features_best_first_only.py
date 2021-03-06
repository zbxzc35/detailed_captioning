'''Author: Brandon Trabucco, Copyright 2019
Load the MSCOCO dataset serialized to tensorflow sequence examples.'''


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


import tensorflow as tf


def _load_dataset_from_tf_records(mode, is_mini):
    assert(mode in ["train", "eval", "test"])
    if mode == "train":
        input_file_pattern = "data/coco_best_first{0}/train-?????-of-?????".format("_mini" if is_mini else "")
    if mode == "eval":
        input_file_pattern = "data/coco_best_first{0}/val-?????-of-?????".format("_mini" if is_mini else "")
    if mode == "test":
        input_file_pattern = "data/coco_best_first{0}/test-?????-of-?????".format("_mini" if is_mini else "")
    data_files = tf.data.Dataset.list_files(input_file_pattern)
    return data_files.apply(tf.contrib.data.parallel_interleave(
        tf.data.TFRecordDataset, cycle_length=4, sloppy=True))


def _process_tf_record_proto(serialized_proto):
    context, sequence = tf.parse_single_sequence_example(
        serialized_proto,
        context_features = {
            "image/image_id": tf.FixedLenFeature([], dtype=tf.int64),
            "image/previous_id": tf.FixedLenFeature([], dtype=tf.int64),
            "image/next_id": tf.FixedLenFeature([], dtype=tf.int64),
            "image/pointer": tf.FixedLenFeature([], dtype=tf.int64)},
        sequence_features = {
            "image/running_ids": tf.FixedLenSequenceFeature([], dtype=tf.int64),
            "image/image_features": tf.FixedLenSequenceFeature([], dtype=tf.float32)})
    image_id, running_ids = (
        context["image/image_id"], sequence["image/running_ids"])
    previous_id, next_id, pointer = (
        context["image/previous_id"], context["image/next_id"], context["image/pointer"])
    image_features = sequence["image/image_features"]
    return {"image_id": image_id, "running_ids": running_ids, 
            "previous_id": previous_id, "next_id": next_id, "pointer": pointer,
            "image_features": image_features}


def _mask_and_slice(x):
    image_id, running_ids, image_features = x["image_id"], x["running_ids"], x["image_features"]
    previous_id, next_id, pointer = x["previous_id"], x["next_id"], x["pointer"]
    caption_length = tf.shape(running_ids)[0]
    indicator = tf.ones(tf.expand_dims(caption_length, 0), dtype=tf.int32)
    return {"image_id": image_id, "running_ids": running_ids, "indicator": indicator, 
            "previous_id": previous_id, "next_id": next_id, "pointer": pointer,
            "image_features": image_features}


def _prepare_final_batch(x):
    image_id, running_ids, indicator, previous_id, next_id, pointer, image_features = (
        x["image_id"], x["running_ids"], x["indicator"], 
        x["previous_id"], x["next_id"], x["pointer"], x["image_features"])
    target_shape = [tf.shape(image_features)[0], 7, 7, 2048]
    image_features = tf.reduce_mean(tf.reshape(image_features, target_shape), [1, 2])
    image_id = tf.cast(image_id, tf.int32)
    running_ids = tf.cast(running_ids, tf.int32)
    indicator = tf.cast(indicator, tf.float32)
    previous_id = tf.cast(previous_id, tf.int32)
    next_id, pointer = tf.cast(next_id, tf.int32), tf.cast(pointer, tf.int32)
    image_features = tf.cast(image_features, tf.float32)
    return {"image_id": image_id, "running_ids": running_ids, "indicator": indicator, 
            "previous_id": previous_id, "next_id": next_id, "pointer": pointer,
            "image_features": image_features}
    

def import_mscoco(mode="train", is_mini=True, batch_size=100, num_epochs=1):
    is_training = (mode == "train")
    dataset = _load_dataset_from_tf_records(mode, is_mini)
    dataset = dataset.map(_process_tf_record_proto, num_parallel_calls=4)
    dataset = dataset.map(_mask_and_slice, num_parallel_calls=4)
    dataset = dataset.apply(tf.contrib.data.shuffle_and_repeat(1000, count=num_epochs))
    padded_shapes = {"image_id": [], "running_ids": [None], "indicator": [None], 
                     "previous_id": [], "next_id": [], "pointer": [], 
                     "image_features": [7 * 7 * 2048]}
    dataset = dataset.padded_batch(batch_size, padded_shapes=padded_shapes, drop_remainder=True)
    dataset = dataset.map(_prepare_final_batch, num_parallel_calls=4)
    dataset = dataset.apply(tf.contrib.data.prefetch_to_device("/gpu:0", buffer_size=2))
    iterator = dataset.make_one_shot_iterator()
    x = iterator.get_next()
    image_id, running_ids, indicator, previous_id, next_id, pointer, image_features = (
        x["image_id"], x["running_ids"], x["indicator"], 
        x["previous_id"], x["next_id"], x["pointer"], x["image_features"])
    return image_id, running_ids, indicator, previous_id, next_id, pointer, image_features

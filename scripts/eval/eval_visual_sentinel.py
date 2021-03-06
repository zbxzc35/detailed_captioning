'''Author: Brandon Trabucco, Copyright 2019
Test the image captioning model with some fake inputs.'''


import os
import time
import json
import itertools
import tensorflow as tf
import numpy as np
from detailed_captioning.layers.image_captioner import ImageCaptioner
from detailed_captioning.cells.visual_sentinel_cell import VisualSentinelCell
from detailed_captioning.utils import check_runtime
from detailed_captioning.utils import load_glove
from detailed_captioning.utils import load_image_from_path
from detailed_captioning.utils import get_resnet_v2_101_checkpoint
from detailed_captioning.utils import get_visual_sentinel_checkpoint
from detailed_captioning.utils import remap_decoder_name_scope
from detailed_captioning.utils import list_of_ids_to_string
from detailed_captioning.utils import recursive_ids_to_string
from detailed_captioning.utils import coco_get_metrics
from detailed_captioning.utils import get_train_annotations_file
from detailed_captioning.inputs.spatial_image_features_only import import_mscoco


PRINT_STRING = """({3:.2f} img/sec) iteration: {0:05d}\n    caption: {1}\n    label: {2}"""
BATCH_SIZE = 10
BEAM_SIZE = 16


if __name__ == "__main__":
    
    vocab, pretrained_matrix = load_glove(vocab_size=100000, embedding_size=300)
    with tf.Graph().as_default():

        image_id, spatial_features, input_seq, target_seq, indicator = (
            import_mscoco(mode="train", batch_size=BATCH_SIZE, num_epochs=1, is_mini=True))
        image_captioner = ImageCaptioner(VisualSentinelCell(300), vocab, pretrained_matrix, 
            trainable=False, beam_size=BEAM_SIZE)
        logits, ids = image_captioner(spatial_image_features=spatial_features)
        captioner_saver = tf.train.Saver(var_list=remap_decoder_name_scope(image_captioner.variables))
        captioner_ckpt, captioner_ckpt_name = get_visual_sentinel_checkpoint()

        with tf.Session() as sess:

            assert(captioner_ckpt is not None)
            captioner_saver.restore(sess, captioner_ckpt)
            used_ids = set()
            json_dump = []

            for i in itertools.count():
                time_start = time.time()
                try:
                    _ids, _target_seq, _image_id = sess.run([ids, target_seq, image_id])
                except:
                    break
                the_captions = recursive_ids_to_string(_ids[:, 0, :].tolist(), vocab)
                the_labels = recursive_ids_to_string(_target_seq[:, :].tolist(), vocab)
                the_image_ids = _image_id.tolist()
                for j, x, y in zip(the_image_ids, the_captions, the_labels):
                    if not j in used_ids:
                        used_ids.add(j)
                        json_dump.append({"image_id": j, "caption": x})
                print(PRINT_STRING.format(i, the_captions[0], the_labels[0], 
                    BATCH_SIZE / (time.time() - time_start))) 

            print("Finishing evaluating.")
            coco_get_metrics(json_dump, "ckpts/visual_sentinel/", get_train_annotations_file())

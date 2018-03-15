""" Testing Persephone on Alex/Steven's Kunwinjku data. """

import collections
import copy
import logging
import os
from os.path import splitext
from os.path import join
from pathlib import Path
import pprint
import random
import subprocess
from typing import List, Sequence

import pint
import pytest
from pympi.Elan import Eaf

from persephone import config
from persephone import corpus
from persephone import distance
from persephone import utterance
from persephone.utterance import Utterance
from persephone.datasets import bkw
from persephone.preprocess import elan
from persephone.corpus_reader import CorpusReader
from persephone.run import prep_exp_dir, prep_sub_exp_dir
from persephone import rnn_ctc
from persephone import utils
from persephone import results

ureg = pint.UnitRegistry()

logging.config.fileConfig(config.LOGGING_INI_PATH)

@pytest.mark.experiment
class TestBKWExperiment:

    @pytest.fixture
    def clean_git(self):
        utils.is_git_directory_clean(".")

    def test_tf_gpu(self):
        import tensorflow as tf
        # Creates a graph.
        a = tf.constant([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], shape=[2, 3], name='a')
        b = tf.constant([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], shape=[3, 2], name='b')
        c = tf.matmul(a, b)
        # Creates a session with log_device_placement set to True.
        sess = tf.Session(config=tf.ConfigProto(log_device_placement=True))
        # Runs the op.
        print(sess.run(c))

    @staticmethod
    def train_bkw(num_layers: int) -> None:
        exp_dir = prep_exp_dir(directory=config.TEST_EXP_PATH)
        corp = bkw.create_corpus(tgt_dir=Path(config.TEST_DATA_PATH) / "bkw")
        cr = CorpusReader(corp)
        model = rnn_ctc.Model(exp_dir, cr, num_layers=num_layers, hidden_size=250)
        model.train(min_epochs=40)

    def test_bkw_2_layers(self, clean_git):
        """ Trains a multispeaker BKW system using default settings. """
        self.train_bkw(num_layers=2)

    def test_bkw_3_layers(self, clean_git):
        """ Trains a multispeaker BKW system using default settings. """
        self.train_bkw(num_layers=3)

@pytest.mark.experiment
class TestBKW:

    tgt_dir = Path(config.TEST_DATA_PATH) / "bkw"
    en_words_path = Path(config.EN_WORDS_PATH)
    NUM_UTTERS = 1004 # Or 1006?
    NUM_SPEAKERS = 19

    @pytest.fixture(scope="class")
    def prep_org_data(self):
        """ Ensure the un-preprocessed data is available. """

        # Ensure the BKW data is all there
        bkw_path = Path(config.BKW_PATH)
        if not bkw_path.is_dir():
            raise NotImplementedError(
                "Data isn't available in {} and I haven't figured out how authentication".format(bkw_path) +
                " should best work for datasets that aren't yet public.")
        assert bkw_path.is_dir()

        # Ensure english-words/words.txt is there.
        assert self.en_words_path.is_file()

        return bkw_path

    @pytest.fixture
    def clean_tgt_dir(self):
        """ Clears the target testing directory. """

        if self.tgt_dir.is_dir():
            import shutil
            shutil.rmtree(str(self.tgt_dir))

        assert not self.tgt_dir.is_dir()

    @pytest.fixture
    def preprocessed_corpus(self, prep_org_data):
        """ Ensure's corpus preprocessing happens before any of the tests
        run that rely on it"""
        return bkw.create_corpus(tgt_dir=self.tgt_dir)

    def check_corpus(self, corp):

        assert len(corp.utterances) == self.NUM_UTTERS

        # Below tests might not work since filtering of utterances by size 
        #assert len(corp.get_train_fns()[0] +
        #           corp.get_valid_fns()[0] +
        #           corp.get_test_fns()[0]) == self.NUM_UTTERS
        #assert len(corp.determine_prefixes()) == self.NUM_UTTERS
        #assert (self.tgt_dir / "wav").is_dir()
        #assert len(list(corp.wav_dir.iterdir())) == self.NUM_UTTERS

    @pytest.mark.slow
    def test_bkw_preprocess(self, prep_org_data, clean_tgt_dir, preprocessed_corpus):
        self.check_corpus(preprocessed_corpus)

    def test_bkw_after_preprocessing(self, preprocessed_corpus):
        self.check_corpus(preprocessed_corpus)

    @staticmethod
    def count_empty(utterances: List[Utterance]) -> int:
        empty_count = 0
        for utter in utterances:
            if utter.text.strip() == "":
                empty_count += 1
        return empty_count

    def test_utterances_from_dir(self, prep_org_data):
        bkw_org_path = prep_org_data

        utterances = elan.utterances_from_dir(bkw_org_path, ["xv"])
        assert len(utterances) == 1036
        assert len(utterance.remove_empty_text(utterances)) == 1035
        assert len(utterance.remove_duplicates(utterances)) == 1029
        assert len(utterance.remove_duplicates(
                                   utterance.remove_empty_text(utterances))) == 1028

        utterances = elan.utterances_from_dir(bkw_org_path, ["rf"])
        assert len(utterances) == 1242
        assert len(utterance.remove_empty_text(utterances)) == 631
        assert len(utterance.remove_duplicates(utterances)) == 1239
        assert len(utterance.remove_duplicates(
                                   utterance.remove_empty_text(utterances))) == 631

        utterances = elan.utterances_from_dir(bkw_org_path, ["rf", "xv"])
        assert len(utterances) == 2278
        assert len(utterance.remove_empty_text(utterances)) == 1666
        assert len(utterance.remove_duplicates(utterances)) == 1899
        assert len(utterance.remove_duplicates(
                                   utterance.remove_empty_text(utterances))) == 1291

    @staticmethod
    def check_text_in_utters(text: str, utters: List[Utterance]) -> bool:
        """ Checks that the target text is found in utterances. """
        for utter in utters:
            if utter.text == text:
                return True
        return False

    def test_mark_on_rock_rf_xv_duplicate(self, prep_org_data):
        mark_on_rock_path = prep_org_data / "Mark on Rock.eaf"
        anbuyika_text = (" Anbuyika rudno karudyo mani arriwa::::m"
                         " arribebmeng Madjinbardi")

        xv_utters = elan.utterances_from_eaf(mark_on_rock_path, ["xv"])
        rf_utters = elan.utterances_from_eaf(mark_on_rock_path, ["rf"])
        xv_rf_utters = elan.utterances_from_eaf(mark_on_rock_path, ["xv", "rf"])

        assert self.check_text_in_utters(anbuyika_text, xv_utters)
        assert self.check_text_in_utters(anbuyika_text, rf_utters)
        assert self.check_text_in_utters(anbuyika_text, xv_rf_utters)
        assert not self.check_text_in_utters("some random text", xv_rf_utters)

        assert len(xv_utters) == 425
        assert len(rf_utters) == 420
        assert len(xv_rf_utters) == 845
        assert len(utterance.remove_duplicates(xv_rf_utters)) == 476
        assert len(utterance.remove_empty_text(
                   utterance.remove_duplicates(xv_rf_utters))) == 473

    def test_corpus_duration(self, preprocessed_corpus):
        corp = preprocessed_corpus
        cr = CorpusReader(corp, batch_size=1)
        cr.calc_time()
        print("Number of corpus utterances: {}".format(len(corp.get_train_fns()[0])))

    def test_explore_code_switching(self, prep_org_data):
        bkw_org_path = prep_org_data
        utterances = elan.utterances_from_dir(bkw_org_path, ["rf", "xv"])
        utterances = utterance.remove_empty_text(
                     utterance.remove_duplicates(utterances))
        codeswitched_path = self.tgt_dir / "codeswitched.txt"
        bkw.explore_code_switching(utterances, codeswitched_path)

    def test_speaker_id(self, prep_org_data):
        bkw_org_path = prep_org_data
        utterances = elan.utterances_from_dir(bkw_org_path, ["rf", "xv"])
        no_speaker_tiers = set()
        speaker_tiers = set()
        speakers = set()
        for utter in utterances:
            tier_id = splitext(utter.prefix)[0]
            if utter.speaker == None:
                no_speaker_tiers.add(tier_id)
            else:
                speaker_tiers.add((tier_id, utter.speaker))
                speakers.add(utter.speaker)

        assert len(no_speaker_tiers) == 0
        assert len(speakers) == self.NUM_SPEAKERS

    def test_overlapping_utters(self, prep_org_data):
        tier1 = "rf"
        tier2 = "rf@MN"
        eaf_path = prep_org_data / "Marys_Yirlinkirrkirr.eaf"
        eaf = Eaf(str(eaf_path))
        #import pprint
        #pprint.pprint(list(eaf.get_gaps_and_overlaps(tier1, tier2)))

    def test_speaker_durations(self, prep_org_data):
        bkw_org_path = prep_org_data
        utterances = elan.utterances_from_dir(bkw_org_path, ["rf", "xv"])
        print(len(utterances))
        utterances = utterance.remove_empty_text(utterances)
        print(len(utterances))
        utterances = utterance.remove_duplicates(utterances)
        print(len(utterances))
        utterances = [utter for utter in utterances if bkw.bkw_filter(utter)]
        print(len(utterances))
        utterances = [utter for utter in utterances if utterance.duration(utter) < 10000]
        total = 0
        fmt = "{:20}{:10}"
        dur_fmt = "{:<10.3f}"
        print(fmt.format("Speaker", "Duration"))
        for speaker, duration in sorted(
                                      utterance.speaker_durations(utterances),
                                      key=lambda x: x[1],
                                      reverse=True):
            dur_mins = (duration * ureg.milliseconds).to(ureg.minutes).magnitude
            dur_str = dur_fmt.format(dur_mins)
            total += dur_mins
            print(fmt.format(speaker, dur_str))
        print(fmt.format("Total", dur_fmt.format(total)))

    @pytest.mark.skip
    def test_poly_durations(self, prep_org_data):
        bkw_org_path = prep_org_data
        utterances = elan.utterances_from_dir(bkw_org_path, ["rf", "xv"])
        print("Total duration of utterances is {}".format(
            utterance.duration(utterances)))
        print("Total duration of the first utterance is {}".format(
            utterance.duration(utterances[0])))

    def test_train_data_isnt_test_data(self, preprocessed_corpus):

        corp = preprocessed_corpus

        # Assert test fns are distinct from train fns.
        train = set(corp.get_train_fns()[0])
        valid = set(corp.get_valid_fns()[0])
        test = set(corp.get_test_fns()[0])
        print(len(train))
        print(len(valid))
        print(len(test))
        assert train - valid == train
        assert train - test == train
        assert valid - train == valid
        assert valid - test == valid
        assert test - train == test
        assert test - valid == test

        # First assert that test corpus utterances aren't in the training set
        # by loading them.
        #train = []
        #for fn in corp.get_train_fns():
        #    with open(fn) as f:
        #        train.append(read().strip())
        #valid = []
        #for fn in corp.get_valid_fns():
        #    with open(fn) as f:
        #        valid.append(read().strip())
        #test = []
        #for fn in corp.get_test_fns():
        #    with open(fn) as f:
        #        test.append(read().strip())
        #validtest = valid + test
        #print(train)
        #print(validtest)

        # Could try this at the corpus_reader level, though I need to figure
        # out how that code works again.
        #cr = CorpusReader(corp)
        #for batch in cr.train_batch_gen():
        #    print(batch)
        #    print(cr.human_readable(batch))

        # Then do the more important test of checking for duplicates again. For
        # each utterance in the test set, look for the most similar one
        # edit-distance-wise from the training set. Do the same for the
        # validation set.

        # Do a code review to ensure I'm doing nothing silly.

        # Run another model for unbounded epochs to see if training error
        # diverges from test error.

    @pytest.mark.slow
    def test_multispeaker(self, preprocessed_corpus):
        """ Trains a multispeaker BKW system using default settings. """

        exp_dir = prep_exp_dir(directory=config.TEST_EXP_PATH)
        # TODO bkw.Corpus and elan.Corpus should take an org_dir argument.
        corp = preprocessed_corpus
        cr = CorpusReader(corp)
        model = rnn_ctc.Model(exp_dir, cr, num_layers=2, hidden_size=250)
        model.train(min_epochs=30)

    @pytest.mark.skip
    def test_utt2spk(self, prep_org_data):
        corp = bkw.create_corpus(tgt_dir=self.tgt_dir, speakers=["Mark Djandiomerr"])
        assert len(corp.speakers) == 1
        assert len(corp.get_train_fns()) < self.NUM_UTTERS / 2
        corp = bkw.create_corpus(tgt_dir=self.tgt_dir)
        assert len(corp.speakers) == self.NUM_SPEAKERS
        assert len(corp.get_train_fns()) == self.NUM_UTTERS

    def test_deterministic(self, prep_org_data):
        """ Ensures loading and processing utterences from ELAN files is
        deterministic.
        """
        bkw_org_path = prep_org_data
        utterances_1 = elan.utterances_from_dir(bkw_org_path, ["rf", "xv"])
        utterances_2 = elan.utterances_from_dir(bkw_org_path, ["rf", "xv"])
        assert utterances_1 == utterances_2
        utterances_1 = [utter for utter in utterances_1 if bkw.bkw_filter(utter)]
        utterances_2 = [utter for utter in utterances_2 if bkw.bkw_filter(utter)]
        assert utterances_1 == utterances_2
        utterances_1 = utterance.remove_duplicates(utterances_1)
        utterances_2 = utterance.remove_duplicates(utterances_2)
        assert utterances_1 == utterances_2
        utterances_1 = [bkw.bkw_label_segmenter.segment_labels(utter) for utter in utterances_1]
        utterances_2 = [bkw.bkw_label_segmenter.segment_labels(utter) for utter in utterances_2]
        assert utterances_1 == utterances_2
        utterances_1 = utterance.remove_empty_text(utterances_1)
        utterances_2 = utterance.remove_empty_text(utterances_2)
        assert utterances_1 == utterances_2

    def test_deterministic_2(self, prep_org_data):
        corp_1 = bkw.create_corpus(tgt_dir=self.tgt_dir)
        # Remove the prefix files.
        os.remove(str(corp_1.train_prefix_fn))
        os.remove(str(corp_1.valid_prefix_fn))
        os.remove(str(corp_1.test_prefix_fn))
        corp_2 = bkw.create_corpus(tgt_dir=self.tgt_dir)
        assert corp_1.utterances != None
        assert corp_1.utterances == corp_2.utterances
        assert len(corp_1.utterances) == self.NUM_UTTERS
        assert set(corp_1.get_train_fns()[0]) == set(corp_2.get_train_fns()[0])
        assert set(corp_1.get_valid_fns()[0]) == set(corp_2.get_valid_fns()[0])
        assert set(corp_1.get_test_fns()[0]) == set(corp_2.get_test_fns()[0])

    def test_empty_wav(self, prep_org_data):
        # Checking the origin of the empty wav.

        bkw_org_path = prep_org_data
        utterances = elan.utterances_from_dir(bkw_org_path, ["rf", "xv"])

        filtered = utterance.remove_too_short(utterances)
        if filtered != utterances:
            diff = set(utterances) - set(filtered)
            print("set(utterances) - set(filtered): {}:\n".format(
                pprint.pformat(diff)))
            assert False

    # TODO This sort of test, and others don't really rely on the BKW data
    # specifically so could be tested elsewhere (in Travis!)
    def test_pickle_corpus(self, preprocessed_corpus):
        corp = preprocessed_corpus
        corp.pickle()
        retrieved_corp = corpus.Corpus.from_pickle(corp.tgt_dir)
        assert corp.utterances == retrieved_corp.utterances
        print(len(retrieved_corp.utterances))

    # TODO I should probably turn this function into a generator
    @staticmethod
    def random_cross_validation_corpora(corpus, k):
        """ Returns k CorpusReader objects, each of which represent the kth fold in
        a random k-fold cross-validation. For the purposes of this, the corpus
        train_fns, valid_fns and test_fns are all merged together and divided up
        into folds."""

        def check_folds(folds):
            prefix_set = set()
            for fold in folds:
                assert prefix_set | set(fold)
                prefix_set.update(set(fold))

        # Need at least separate folds for training, validation and testing.
        assert k >= 3

        # Make k identical copies of the corpus
        corpus_copies = [copy.deepcopy(corpus) for _ in range(k)]

        # Create a set of all prefixes
        all_prefixes = corpus.train_prefixes + corpus.valid_prefixes + corpus.test_prefixes
        all_prefixes = utils.filter_by_size(corpus.feat_dir, all_prefixes, corpus.feat_type,
                                            corpus.max_samples)


        # Slice the prefixes into k folds
        random.shuffle(all_prefixes)
        fold_size = int(len(all_prefixes) / k)
        folds = [all_prefixes[i:i+fold_size] for i in range(0, len(all_prefixes), fold_size)]
        if len(folds) > k:
            # Then merge the last two folds (the number of prefixes didn't divide
            # perfectly into the number of folds
            folds = folds[:-2] + [folds[-2] + folds[-1]]

        check_folds(folds)

        def rotate(l):
            """ Rotates a list by one element. """
            return l[1:] + l[:1]

        # Assign each of the corpus copies a fold
        for i in range(k):
            corpus_copies[i].test_prefixes = folds[0]
            corpus_copies[i].valid_prefixes = folds[1]
            corpus_copies[i].train_prefixes = sum(folds[2:], [])
            folds = rotate(folds)

        return corpus_copies

    def test_random_xv(self, preprocessed_corpus):
        corp = preprocessed_corpus

        exp_dir = prep_exp_dir(directory=config.TEST_EXP_PATH)

        for fold_corpus in self.random_cross_validation_corpora(corp, 20):
            sub_exp_dir = prep_sub_exp_dir(exp_dir)
            with open(join(sub_exp_dir, "valid_prefixes.txt"), "w") as f:
                for prefix in fold_corpus.valid_prefixes:
                    print(prefix, file=f)
            with open(join(sub_exp_dir, "test_prefixes.txt"), "w") as f:
                for prefix in fold_corpus.test_prefixes:
                    print(prefix, file=f)
            cr = CorpusReader(fold_corpus)
            model = rnn_ctc.Model(sub_exp_dir, cr, num_layers=2, hidden_size=250)
            model.train(min_epochs=30)

    @staticmethod
    def context_errors(hyps: Sequence[Sequence[str]],
                       refs: Sequence[Sequence[str]],
                       n: int) -> str:
        """ Presents information about the n-gram reference contexts that beget
        certain errors, where the error is in the middle of the context.

        We might also want to try the clustered errors counting."""

        alignments = [distance.min_edit_distance_align(ref, hyp)
                      for hyp, ref in zip(hyps, refs)]

        def ngram_alignment(alignment, n):

            # Make the n-gram alignments
            alignment_ = []
            for i in range(len(alignment)-n+1):
                alignment_.append(tuple(alignment[i:i+n]))

            # Normalize each arrow into the form (ref_string, hyp_string)
            alignment_1 = [list(zip(*arrow)) for arrow in alignment_]
            return [("".join(arrow[0]), "".join(arrow[1]))
                    for arrow in alignment_1]

        errors = collections.Counter()
        for alignment in alignments:
            alignment__ = ngram_alignment(alignment, n)
            errors.update(alignment__)

        return sorted(errors.items(), key=lambda x:x[1], reverse=True)

    @staticmethod
    def fetch_xv_valid_hyps_refs_prefixes():
        """ Fetches the cross validation results on the validation sets and
        adds it together."""

        refs = []
        hyps = []
        prefixes = []

        exp_path = Path("testing/exp/41/")
        for path in exp_path.iterdir():
            if path.is_dir():
                with (path / "test" / "refs").open() as f:
                    refs.extend(line.strip().split() for line in f.readlines())
                with (path / "test" / "hyps").open() as f:
                    hyps.extend(line.strip().split() for line in f.readlines())
                with (path / "valid_prefixes.txt").open() as f:
                    prefixes.extend(line.strip() for line in f.readlines())

        return hyps, refs, prefixes

    def test_xv_error_stats(self):
        """ Statistics for Task 1 of Steven's: Gathering statistics of the
        types of errors that occur across the whole corpus based on phonemic
        context. Using results of cross-validation run found in
        slug:code/persephone/testing/exp/28/"""

        hyps, refs, _ = self.fetch_xv_valid_hyps_refs_prefixes()

        #print(list(zip(refs, hyps)))
        #print(len(refs))
        print(results.filtered_error_rate(hyps, refs))

        print(results.fmt_confusion_matrix(hyps, refs))

    def test_xv_latex_output(self, preprocessed_corpus):
        """ Stitches together the data from each fold and sorts by prefix."""

        # Get all the validation (ref, hyp)s.
        hyps, refs, prefixes = self.fetch_xv_valid_hyps_refs_prefixes()
        hyps_refs_prefixes = list(zip(hyps, refs, prefixes))

        corp = preprocessed_corpus
        #prefixes = []
        ## Get the prefixes in the same order
        # NOTE can't do this because getting the random xv corpora involves
        # shuffling, so I can't replicate how it was done.
        ##for fold_corpus in self.random_cross_validation_corpora(corp, 20):
        ##    prefixes.extend(fold_corpus.valid_prefixes)

        #assert len(hyps) == len(refs)
        #assert len(hyps) == len(prefixes)
        #hyps_refs_prefixes = zip(hyps, refs, prefixes)
        #print(pprint.pformat(list(hyps_refs_prefixes)))
        #return

        # Find the prefix by searching the utterances.
        # NOTE This is better, but there are plenty of utterances with
        # duplicate text, so it's not perfect.
        #utters = list(corp.utterances)
        #text2prefix = dict()
        #for utter in utters:
        #    text2prefix[utter.text] = utter.prefix
        #hyps_refs_prefixes = []
        #for hyp, ref in zip(hyps, refs):
        #    text = " ".join(ref)
        #    hyps_refs_prefixes.append((hyp, ref, text2prefix[text]))

        def split_utter_id(hyp_ref_prefix_tup):
            _, _, prefix = hyp_ref_prefix_tup
            story_prefix, utter_id = splitext(prefix)
            utter_id = int(utter_id[1:])
            return story_prefix, utter_id

        # Sort by the prefix by number.
        hyps_refs_prefixes.sort(key=lambda entry: split_utter_id(entry))
        hyps, refs, prefixes = zip(*hyps_refs_prefixes)
        results.fmt_latex_output(hyps, refs, prefixes, Path("xv_output.tex"))
        #print(pprint.pformat([prefix for _, _, prefix in hyps_refs_prefixes]))

        # Output latex.
        # NOTE Gah, can't do this unless I re-run the cross validation and store
        # the prefixes.
        # TODO It should be standard to store prefixes when doing an
        # experiment.

        # Calculate error stats by n-gram context.
        with open("xv_errors.txt", "w") as f:
            for n in range(2,8):
                print("{}-gram references:".format(n), file=f)
                align_counts = self.context_errors(hyps, refs, n)
                align_errs = [align_item for align_item in align_counts
                              if align_item[0][0] != align_item[0][1]]
                fmt = "{:>12} {:>12} {:>5}"
                print("", file=f)
                print(fmt.format("Reference", "Hypothesis", "Count"), file=f)
                print("   " + "-"*28, file=f)
                for err in align_errs[:30]:
                    print(fmt.format(err[0][0], err[0][1], err[1]), file=f)
                #print(pprint.pformat(align_errs[:20]))
                print("", file=f)

        # TODO Find the sentences that these errors occurred in?
        # TODO Can also just count the references that have errors; tha would
        # be interesting too.

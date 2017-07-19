#!/usr/bin/env python3
"""
Scan DICOM folder tree for unique series and update protocol translator

The DICOM input directory should be organized as follows:
<DICOM Directory>/
    <SID 1>/
        <Session 1>/
            Session 1 DICOM files ...
        <Session 2>/
            Session 2 DICOM files ...
        ...
    <SID 2>/
        <Session 1>/
            ...

Here, session refers to all scans performed during a given visit.
Typically this can be given a date-string directory name (eg 20161104 etc).

Usage
----
dcm2bids_prep.py -i <DICOM Directory>

Example
----
% dcm2bids.py -i mydicom

Authors
----
Mike Tyszka, Caltech Brain Imaging Center

Dates
----
2017-07-19 JMT Split protocol translator generation from main code

MIT License

Copyright (c) 2017 Mike Tyszka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

__version__ = '0.1'

import os
import sys
import argparse
import shutil
import json
import dicom
from glob import glob


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert DICOM files to BIDS-compliant Nifty structure')
    parser.add_argument('-i', '--indir', default='dicom',
                        help='DICOM input directory with Subject/Session/Image organization [dicom]')

    # Parse command line arguments
    args = parser.parse_args()

    dcm_root_dir = args.indir

    # Load protocol translation and exclusion info from DICOM directory
    # If no translator is present, prot_dict is an empty dictionary
    # and a template will be created in the DICOM directory. This template should be
    # completed by the user and the conversion rerun.
    prot_dict_json = os.path.join(dcm_root_dir, 'Protocol_Translator.json')
    prot_dict = bids_load_prot_dict(prot_dict_json)

    if prot_dict and os.path.isdir(bids_root_dir):

        print('')
        print('------------------------------------------------------------')
        print('Pass 2 : Organizing Nifti data into BIDS directories')
        print('------------------------------------------------------------')
        first_pass = False

    else:

        print('')
        print('------------------------------------------------------------')
        print('Pass 1 : Scan DICOM folders and create dictionary')
        print('------------------------------------------------------------')
        first_pass = True

        series_list = scan_dicom_series(dcm_root_dir)

    # # Initialize BIDS output directory
    # if not first_pass:
    #     participants_fd = bids_init(bids_root_dir)
    #
    # # Loop over subject directories in DICOM root
    # for dcm_sub_dir in glob(dcm_root_dir + '/*/'):
    #
    #     SID = os.path.basename(dcm_sub_dir.strip('/'))
    #
    #     print('')
    #     print('Processing subject ' + SID)
    #
    #     # Loop over session directories in subject directory
    #     for dcm_ses_dir in glob(dcm_sub_dir + '/*/'):
    #
    #         SES = os.path.basename(dcm_ses_dir.strip('/'))
    #
    #         print('  Processing session ' + SES)
    #
    #         # BIDS subject, session and conversion directories
    #         sub_prefix = 'sub-' + SID
    #         ses_prefix = 'ses-' + SES
    #         bids_sub_dir = os.path.join(bids_root_dir, sub_prefix)
    #         bids_ses_dir = os.path.join(bids_sub_dir, ses_prefix)
    #         bids_conv_dir = os.path.join(bids_ses_dir, 'conv')
    #
    #         # Check if subject/session directory exists
    #         # If it doesn't this is a new sub/ses added to the DICOM root and needs conversion
    #
    #         # Safely create BIDS conversion directory and all containing directories as needed
    #         os.makedirs(bids_conv_dir, exist_ok=True)
    #
    #         if first_pass:
    #
    #             # Run dcm2niix conversion into temporary conversion directory
    #             # This relies on the current CBIC branch of dcm2niix which extracts additional DICOM fields
    #             print('  Converting all DICOM images within directory %s' % dcm_ses_dir)
    #             devnull = open(os.devnull, 'w')
    #             subprocess.call(['dcm2niix', '-b', 'y', '-f', '%n--%p--%q--%s', '-o', bids_conv_dir, dcm_ses_dir],
    #                             stdout=devnull, stderr=subprocess.STDOUT)
    #
    #         else:
    #
    #             # Get subject age and sex from representative DICOM header
    #             dcm_info = bids_dcm_info(dcm_ses_dir)
    #
    #             # Add line to participants TSV file
    #             participants_fd.write("sub-%s\t%s\t%s\n" % (SID, dcm_info['Sex'], dcm_info['Age']))
    #
    #         # Run DICOM conversions
    #         bids_run_conversion(bids_conv_dir, first_pass, prot_dict, bids_ses_dir, SID, SES, use_run)
    #
    # if first_pass:
    #     # Create a template protocol dictionary
    #     bids_create_prot_dict(prot_dict_json, prot_dict)
    # else:
    #     # Close participants TSV file
    #     participants_fd.close()

    # Clean exit
    sys.exit(0)


def scan_dicom_series(dcm_dir):
    """
    Scan all DICOM images within the DICOM directory to collect unique series descriptions

    :param dcm_dir:
    :return: series_dict
    """

    series_list = []

    for root, dirs, files in os.walk(dcm_dir):
        path = root.split(os.sep)
        print((len(path) - 1) * '---', os.path.basename(root))
        for file in files:
            print(len(path) * '---', file)

    return series_list


def bids_dcm_info(dcm_dir):
    """
    Extract relevant subject information from DICOM header
    - Assumes only one subject present within dcm_dir

    :param dcm_dir: directory containing all DICOM files or DICOM subfolders
    :return dcm_info: DICOM header information dictionary
    """

    # Init the DICOM structure
    ds = []

    # Init the subject info dictionary
    dcm_info = dict()

    # Walk through dcm_dir looking for valid DICOM files
    for subdir, dirs, files in os.walk(dcm_dir):
        for file in files:

            try:
                ds = dicom.read_file(os.path.join(subdir, file))
            except:
                pass

            # Break out if valid DICOM read
            if ds:
                break

    if ds:

        # Fill dictionary
        # Note that DICOM anonymization tools sometimes clear these fields
        if hasattr(ds, 'PatientSex'):
            dcm_info['Sex'] = ds.PatientSex
        else:
            dcm_info['Sex'] = 'Unknown'

        if hasattr(ds, 'PatientAge'):
            dcm_info['Age'] = ds.PatientAge
        else:
            dcm_info['Age'] = 0

    else:

        print('* No DICOM header information found in %s' % dcm_dir)
        print('* Confirm that DICOM images in this folder are uncompressed')
        print('* Exiting')
        sys.exit(1)

    return dcm_info


def bids_load_prot_dict(prot_dict_json):
    """
    Read protocol translations from JSON file in DICOM directory
    :param prot_dict_json:
    :return:
    """

    if os.path.isfile(prot_dict_json):

        # Read JSON protocol translator
        json_fd = open(prot_dict_json, 'r')
        prot_dict = json.load(json_fd)
        json_fd.close()

    else:

        prot_dict = dict()

    return prot_dict


def bids_create_prot_dict(prot_dict_json, prot_dict):
    """
    Write protocol translation dictionary template to JSON file
    :param prot_dict_json:
    :param prot_dict:
    :return:
    """

    if os.path.isfile(prot_dict_json):

        print('* Protocol dictionary already exists : ' + prot_dict_json)
        print('* Skipping creation of new dictionary')

    else:

        json_fd = open(prot_dict_json, 'w')
        json.dump(prot_dict, json_fd, indent=4, separators=(',', ':'))
        json_fd.close()

        print('')
        print('---')
        print('New protocol dictionary created : %s' % prot_dict_json)
        print('Remember to replace "EXCLUDE" values in dictionary with an appropriate image description')
        print('For example "MP-RAGE T1w 3D structural" or "MB-EPI BOLD resting-state')
        print('---')
        print('')

    return


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()

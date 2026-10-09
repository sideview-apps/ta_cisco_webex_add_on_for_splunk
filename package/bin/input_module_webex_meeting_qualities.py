import json
from datetime import datetime

from webex_constants import (
    _MEETINGS_ENDPOINT,
    _GET_MEETING_QUALITIES,
    _RESPONSE_TAG_MAP
)
from webex_api_client import paging_get_request_to_webex
from oauth_helper import get_valid_access_token
from webex_utils import get_time_span

def collect_events(helper, ew):

    # insert input values into the url and/or header (helper class handles credential store)
    opt_start_time = helper.get_arg('start_time')
    opt_end_time = helper.get_arg('end_time')
    opt_webex_account_region = helper.get_arg('account_region')

    # Get account info
    opt_global_account = helper.get_arg("global_account")
    account_name = opt_global_account.get("name")
    client_id = opt_global_account.get("client_id")
    client_secret = opt_global_account.get("client_secret")
    stored_access_token = opt_global_account.get("access_token")
    stored_refresh_token = opt_global_account.get("refresh_token")
    base_endpoint = opt_global_account.get("endpoint")
    is_gov_account = opt_global_account.get("is_gov_account")

    # check the checkpoint
    # get start time from checkpoint
    last_timestamp_checkpoint_key = "{}_meeting_qualities_last_timestamp".format(
        helper.get_input_stanza_names()
    )

    timestamp = helper.get_check_point(last_timestamp_checkpoint_key)
    helper.log_debug("[-] last time timestamp: {}".format(timestamp))

    start_time, end_time = get_time_span(opt_start_time, opt_end_time, timestamp, "%Y-%m-%dT%H:%M:%SZ")

    #  if start and end time are not returned it means it has completed the ingestion
    if not start_time and not end_time:
        helper.log_info(
            "[-] Finished ingestion for time range {start_time} - {end_time}".format(
                start_time=opt_start_time, end_time=opt_end_time
            )
        )
        return

    access_token, refresh_token = get_valid_access_token(helper, account_name, client_id, client_secret, stored_access_token, stored_refresh_token, base_endpoint)

    # get meeting ids from the list meetings endpoint
    # construct the request params for meetings endpoint
    meetings_params = {"meetingType":"meeting", "state": "ended"}
    meetings_params["from"] = start_time
    meetings_params["to"] = end_time
    helper.log_debug("[-] starting the ingestion for range [{start_time} - {end_time}]".format(start_time=meetings_params["from"], end_time=meetings_params["to"]))
    
    meetings = paging_get_request_to_webex(
        helper,
        base_endpoint,
        _MEETINGS_ENDPOINT,
        access_token,
        refresh_token,
        account_name,
        client_id,
        client_secret,
        meetings_params,
        _RESPONSE_TAG_MAP[_MEETINGS_ENDPOINT],
    )
    
    helper.log_debug("[-] meetings data size: {}".format(len(meetings)))

    write_meeting_instances(helper, ew, meetings, opt_start_time)

    # retrieve the meeting qualities data for each meeting
    latest_time = None
    account_region = "gov" if is_gov_account == "1" else opt_webex_account_region
    
    for meeting in meetings:
        # only ingest the meetings that happened after the last checkpoint time
        # compare the meeting start time with the last checkpoint time
        last_checkpoint_time = opt_start_time if not helper.get_check_point(last_timestamp_checkpoint_key) else helper.get_check_point(last_timestamp_checkpoint_key)
        last_checkpoint_time = datetime.strptime(last_checkpoint_time,"%Y-%m-%dT%H:%M:%SZ")
        meeting_start_time = datetime.strptime(meeting["start"], "%Y-%m-%dT%H:%M:%SZ")
        helper.log_debug("[-] meeting_start_time: {} vs last_checkpoint_time: {}".format(meeting_start_time, last_checkpoint_time))

        if meeting_start_time > last_checkpoint_time and meeting.get("id", None):
            meetings_qualities_params = {"meetingId": meeting["id"], "max": 1000}
            # A single meeting's qualities fetch can fail transiently (e.g. Webex 502) or
            # PERMANENTLY: quality data expires 14 days after the meeting, after which this
            # endpoint returns 425 ("Quality data is not available for this meeting because
            # it has expired after 14 days") on every call, forever. Do NOT let one meeting
            # abort the whole run: that skips save_check_point() below, so the checkpoint
            # never advances and EVERY meeting in the window is re-ingested on every interval
            # (unbounded duplicates). Log and skip this meeting; the checkpoint still advances
            # past it via the other meetings in the window. Trade-off: a persistently-failing
            # meeting's qualities are not captured -- acceptable vs. stalling all meetings.
            try:
                meetings_qualities_data_list = paging_get_request_to_webex(
                    helper,
                    base_endpoint,
                    _GET_MEETING_QUALITIES,
                    access_token,
                    refresh_token,
                    account_name,
                    client_id,
                    client_secret,
                    meetings_qualities_params,
                    _RESPONSE_TAG_MAP[_GET_MEETING_QUALITIES],
                    webex_account_region=account_region
                )
            except Exception as e:
                helper.log_error(
                    "[-] Skipping meeting {} for this run due to qualities API error: {}".format(meeting["id"], e)
                )
                continue
            helper.log_debug("[-] meetings qualities data list size: {} for meeting: {}".format(len(meetings_qualities_data_list), meeting["id"]))

            if len(meetings_qualities_data_list) > 0:
                # write the meeting qualities data into Splunk
                try:
                    for meetings_quality in meetings_qualities_data_list:
                        # set the joinTime as event timestamp
                        event_start_time = datetime.strptime(meetings_quality["joinTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
                        event_time = (event_start_time - datetime(1970, 1, 1)).total_seconds()

                        meeting_quality_event = helper.new_event(
                            source=helper.get_input_type() + "://" + helper.get_input_stanza_names(),
                            index=helper.get_output_index(),
                            sourcetype="cisco:webex:meeting:qualities",
                            data=json.dumps(meetings_quality),
                            time=event_time,
                        )
                        ew.write_event(meeting_quality_event)
                except Exception as e:
                    # Same rationale as the fetch above: a write/parse failure for one
                    # meeting must not abort the run and block the checkpoint save. Log
                    # and move on to the next meeting.
                    helper.log_error("[-] Error happened while writing meetings qualities into Splunk for meeting {}: {}".format(meeting["id"], e))
                    continue
                latest_time = last_checkpoint_time if latest_time is None else latest_time
                latest_time = max(latest_time, meeting_start_time)

    # save the latest meeting start time as checkpoint for next ingestion
    if latest_time:
        helper.save_check_point(last_timestamp_checkpoint_key, latest_time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        helper.log_debug("[-] Saved checkpoint: Last run time saved: {}".format(helper.get_check_point(last_timestamp_checkpoint_key)))

def write_meeting_instances(helper, ew, meetings, opt_start_time):
    """
    Write each ended meeting instance as an event of its own.

    The list above is fetched only to get the ids to ask for qualities with, but
    each instance is worth keeping in its own right.  It is the one record that
    carries all three of a meeting's ids: its own id ("<series>_I_<n>", the same
    value the qualities call meetingInstanceId and the usage and attendee
    reports call meetingId), meetingSeriesId, and scheduledMeetingId, which is
    the id the scheduled meeting has in cisco:webex:meetings.  Nothing else
    links a meeting that happened to the meeting that was scheduled.  It is
    also the only record of an ad-hoc or Personal Room meeting that had no
    quality data, since those never appear among the scheduled meetings.

    It has a checkpoint of its own, so that the qualities checkpoint below keeps
    exactly the behaviour it had.  That one only advances past a meeting once
    its qualities were written, so a meeting with none is seen again on the next
    run, and an instance written from that loop would be written again too.
    """
    checkpoint_key = "{}_meeting_instances_last_timestamp".format(
        helper.get_input_stanza_names()
    )
    checkpoint_value = helper.get_check_point(checkpoint_key) or opt_start_time
    last_checkpoint_time = datetime.strptime(checkpoint_value, "%Y-%m-%dT%H:%M:%SZ")
    latest_time = None

    for meeting in meetings:
        try:
            meeting_start_time = datetime.strptime(meeting["start"], "%Y-%m-%dT%H:%M:%SZ")
            if meeting_start_time <= last_checkpoint_time or not meeting.get("id", None):
                continue
            event_time = (meeting_start_time - datetime(1970, 1, 1)).total_seconds()
            meeting_instance_event = helper.new_event(
                source=helper.get_input_type() + "://" + helper.get_input_stanza_names(),
                index=helper.get_output_index(),
                sourcetype="cisco:webex:meeting:instances",
                data=json.dumps(meeting),
                time=event_time,
            )
            ew.write_event(meeting_instance_event)
        except Exception as e:
            # One bad record must not stop the rest, nor the checkpoint save.
            helper.log_error("[-] Error happened while writing meeting instance {} into Splunk: {}".format(meeting.get("id"), e))
            continue
        latest_time = meeting_start_time if latest_time is None else max(latest_time, meeting_start_time)

    if latest_time:
        helper.save_check_point(checkpoint_key, latest_time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        helper.log_debug("[-] Saved meeting instances checkpoint: {}".format(helper.get_check_point(checkpoint_key)))

import sys
assert sys.version_info >= (3, 9), "incompatible python version"
import os
import logging

import google.auth
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

RO_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
RW_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_creds(scopes):
    # creds, _ = google.auth.default()
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    tokenfile_path = os.path.expanduser("~/.credentials/repo_metadata.json")
    if os.path.exists(tokenfile_path):
        creds = Credentials.from_authorized_user_file(tokenfile_path, scopes)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.expanduser("~/.credentials/credentials.json"), scopes,
                redirect_uri=os.environ.get("REDIRECT_URI"),
            )
            # flow.oauth2session.access_type = "offline"
            print(flow.authorization_url(access_type="offline", prompt="consent")[0])
            print("\n")

            code = input('Enter the authorization code: ')
            flow.fetch_token(code=code)
            creds = flow.credentials
            # creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
        with open(tokenfile_path, "w") as token:
            token.write(creds.to_json())
    return creds

class Sheet(object):
    def __init__(self, spreadsheet_id, sheet_index=0):
        self.spreadsheet_id = spreadsheet_id
        self.creds = get_creds(RW_SCOPES)
        self.service = build("sheets", "v4", credentials=self.creds)

        self.rows = []
        self.headers = []
        self.updates = []

        spreadsheet = (
            self.service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id)
            .execute()
        )
        logging.info('spreadsheet: %r', spreadsheet["sheets"][sheet_index])
        self.first_sheet = spreadsheet["sheets"][0]['properties']['title']

        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range="'%s'" % self.first_sheet)
            .execute()
        )
        # logging.info('result: %r', result)
        rows = result.get("values", [])
        # logging.info("found %r rows", len(rows))
        for i, row in enumerate(rows):
            if not self.headers:
                self.headers = row
                self.rows.append(self.headers[0])
            else:
                # logging.info('row[%d]: %r', i, row[0] )
                self.rows.append(row[0])
            # logging.info("%r", row)

        logging.debug('headers: %r', self.headers)
        logging.debug("found %d rows %r", len(self.rows), self.rows)

    def update_cell(self, row, column, value):
        try:
            rowNumber = self.rows.index(row) + 1
            columnName = _b26(self.headers.index(column) + 1)
        except ValueError:
            logging.warning("not found %s:%r:%r", self.first_sheet, column, row)
            return
        range_ = "'%s'!%s%d" % (self.first_sheet, columnName, rowNumber)

        # logging.info("setting %s:%r [%r:%r] to %r", self.first_sheet, range_, column, row, value)
        self.updates.append({
            "range": range_,
            "values": [[value]],
        })
        # self.service.spreadsheets().values().update(
        #     spreadsheetId=self.spreadsheet_id, range=range_,
        #     valueInputOption='RAW',
        #     body={'values': [[value]]}).execute()

    def batch_update(self):
        if not self.updates:
            return
        logging.info("batch_update %d updates", len(self.updates))
        body = {
            "valueInputOption": "RAW",
            "data": self.updates,
        }
        result = (
            self.service.spreadsheets()
            .values()
            .batchUpdate(spreadsheetId=self.spreadsheet_id, body=body)
            .execute()
        )
        self.updates = []

def _b26(n):
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result
#!/usr/bin/env python3
import argparse
import base64
import csv
import glob
import io
import json
import smtplib
import sys
from tkinter.messagebox import NO
import uuid
from email.headerregistry import Address
from email.message import EmailMessage
from typing import List, Optional

import frontmatter
import jinja2
import pandas as pd
import qrcode


def generate_clients(contacts) -> str:
    clients_config = ',\n'.join(contacts.apply(lambda contact: f'''\
{{
  "email": "{contact['email']}",
  "id": "{contact['uuid']}",
  "level": 0,
  "alterId": 4
}}''', axis=1))
    return f"[{clients_config}]"


def generate_vmess_url(config, id_: str) -> str:
    v2_config = config['v2']
    v2_config['id'] = id_
    return 'vmess://' + base64.b64encode(json.dumps(v2_config).encode()).decode()


def generate_uuid(namespace: uuid.UUID, email: str) -> uuid.UUID:
    return uuid.uuid5(namespace, email)


def load_config(filename: str):
    with open(filename) as f:
        return json.load(f)


def load_contacts(filename: str, data: Optional[str] = None):
    contacts = pd.read_csv(filename)
    if data is not None:
        for extra in glob.iglob(f'{data}/**/*.csv', recursive=True):
            contacts = pd.merge(contacts, pd.read_csv(
                extra), on='email', how='left')
    return contacts


def run_init(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contacts = load_contacts(args.contacts)
    namespace = uuid.UUID(config['namespace'])
    contacts['uuid'] = contacts['email'].map(
        lambda x: generate_uuid(namespace, x))
    if args.write_contacts:
        contacts.to_csv(args.contacts, index=False)
    clients_config = generate_clients(contacts)
    print(clients_config)


def run_send(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contacts = load_contacts(args.contacts, args.data)
    if args.filter_email:
        contacts = contacts[contacts['email'].isin(args.filter_email)]
    if args.filter_tag:
        contacts = contacts[contacts['tag'].isin(args.filter_tag)]
    email = config['smtp']
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(
        args.templates), autoescape=jinja2.select_autoescape())
    txt_template = env.get_template(f'{args.template}/template.txt')
    html_template = env.get_template(f'{args.template}/template.html')
    msgs: List[EmailMessage] = []
    for _, contact in contacts.iterrows():
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            print(contact)
        reply = input('Resume (y/N): ')
        if reply.lower() != 'y':
            sys.exit(1)
        txt = frontmatter.loads(txt_template.render(contact.to_dict()))
        msg = EmailMessage()
        msg.set_charset('utf-8')
        msg['Subject'] = txt['subject']
        msg['From'] = Address(email['name'], *email['user'].split('@'))
        msg['To'] = (Address(contact['english_name'],
                     *contact['email'].split('@')),)
        msg.set_content(str(txt))
        msg.add_alternative(html_template.render(
            contact.to_dict()), subtype='html')
        if txt.get('attach_vmess', False):
            vmess = generate_vmess_url(config, contact['uuid'])
            qr_img = qrcode.make(vmess)
            qr_img_bytes_io = io.BytesIO()
            qr_img.save(qr_img_bytes_io, format='PNG')
            qr_img_bytes = qr_img_bytes_io.getvalue()
            msg.add_attachment(vmess.encode(), maintype='text',
                               subtype='plain', filename='vmess.txt')
            msg.add_attachment(qr_img_bytes, maintype='image',
                               subtype='png', filename='vmess.png')
        msgs.append(msg)
        print()
    with smtplib.SMTP_SSL(email['server'], email.get('port', 465)) as smtp:
        smtp.login(email['user'], email['password'])
        for msg in msgs:
            smtp.send_message(msg)


def main():
    main_parser = argparse.ArgumentParser()
    main_parser.add_argument('--config', type=str,
                             default='config.json', help='configuration file')
    main_parser.add_argument('--contacts', type=str,
                             default='contacts.csv', help='contacts file')
    main_parser.add_argument('--templates', type=str,
                             default='templates', help='directory to templates')
    main_parser.add_argument('--data', type=str,
                             default='data', help='additional data')
    sub_parsers = main_parser.add_subparsers(
        title='command', help='available sub-commands')
    # init
    parser_init = sub_parsers.add_parser('init', help='generate v2ray config')
    parser_init.add_argument(
        '--write_contacts', action='store_true', help='write back IDs to contacts file')
    parser_init.set_defaults(func=run_init)
    # send
    parser_email = sub_parsers.add_parser('send', help='send emails')
    parser_email.add_argument(
        'template', help='the template used to compose email')
    parser_email.add_argument(
        '--filter_email', action='append', default=[], help='filter emails')
    parser_email.add_argument(
        '--filter_tag', action='append', default=[], help='filter tags')
    # parser_email.add_argument(
    #     '--attach', action='store_true', help='send attachment')
    parser_email.set_defaults(func=run_send)

    args = main_parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        main_parser.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import base64
import csv
import io
import json
import os
import smtplib
import uuid
from email.headerregistry import Address
from email.message import EmailMessage
from typing import List

import qrcode


def generate_clients(clients: List[uuid.UUID], contacts) -> str:
    clients_config = ',\n'.join([f'''\
{{
  "email": "{contact['email']}",
  "id": "{client}",
  "level": 0,
  "alterId": 4
}}''' for client, contact in zip(clients, contacts)])
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


def load_contacts(filename: str):
    with open(filename) as f:
        iterator = iter(csv.reader(f))
        header = next(iterator)
        return [dict(zip(header, row)) for row in iterator]


def run_init(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contacts = load_contacts(args.contacts)
    namespace = uuid.UUID(config['namespace'])
    header = list(contacts[0].keys())
    clients: List[uuid.UUID] = []
    for contact in contacts:
        id_ = generate_uuid(namespace, contact['email'])
        contact['uuid'] = str(id_)
        clients.append(id_)
    if args.write_contacts:
        with open(args.contacts, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for contact in contacts:
                writer.writerow([contact[item] for item in header])
    clients_config = generate_clients(clients, contacts)
    print(clients_config)


def run_email(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contacts = load_contacts(args.contacts)
    if args.filter_email:
        contacts = [
            contact for contact in contacts if contact['email'] in args.filter_email]
    if args.filter_tag:
        contacts = [
            contact for contact in contacts if contact['tag'] in args.filter_tag]
    email = config['smtp']
    with open(os.path.join('templates', args.template, 'subject.txt')) as f:
        subject = f.read().strip()
    with open(os.path.join('templates', args.template, 'template.txt')) as f:
        txt_template = f.read()
    with open(os.path.join('templates', args.template, 'template.html')) as f:
        html_template = f.read()
    msgs: List[EmailMessage] = []
    for contact in contacts:
        print(contact['email'])
    reply = input('Resume (y/N): ')
    if reply.lower() != 'y':
        return
    for contact in contacts:
        msg = EmailMessage()
        msg.set_charset('utf-8')
        msg['Subject'] = subject
        msg['From'] = Address(email['name'], *email['user'].split('@'))
        msg['To'] = (Address(contact['english_name'],
                     *contact['email'].split('@')),)
        params = {
            **contact,
        }
        msg.set_content(txt_template.format(**params))
        msg.add_alternative(html_template.format(**params), subtype='html')
        if args.attach:
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
    sub_parsers = main_parser.add_subparsers(
        title='command', help='available sub-commands')
    # init
    parser_init = sub_parsers.add_parser('init', help='generate v2ray config')
    parser_init.add_argument(
        '--write_contacts', action='store_true', help='write back IDs to contacts file')
    parser_init.set_defaults(func=run_init)
    # notify config
    parser_email = sub_parsers.add_parser(
        'send', help='notify users of their v2ray config')
    parser_email.add_argument(
        'template', help='the template used to compose email')
    parser_email.add_argument(
        '--filter_email', action='append', default=[], help='filter emails')
    parser_email.add_argument(
        '--filter_tag', action='append', default=[], help='filter tags')
    parser_email.add_argument(
        '--attach', action='store_true', help='send attachment')
    parser_email.set_defaults(func=run_email)

    args = main_parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        main_parser.print_help()


if __name__ == "__main__":
    main()

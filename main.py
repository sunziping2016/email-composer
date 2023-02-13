#!/usr/bin/env python3
import argparse
import base64
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


def load_config(filename: str):
    with open(filename) as f:
        return json.load(f)


def load_contacts(args):
    contacts = pd.read_csv(args.contacts)
    for extra in glob.iglob(f'{args.data}/**/*.csv', recursive=True):
        contacts = pd.merge(contacts, pd.read_csv(extra),
                            on='email', how='left')
    if args.email:
        contacts = contacts[contacts['email'].isin(args.email)]
    if args.tag:
        contacts = contacts[contacts['tag'].isin(args.tag)]
    return contacts


def create_env(args, config, contacts):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('.'), autoescape=jinja2.select_autoescape())
    env.globals.update(config)
    env.globals.update({
        "contacts": [row.to_dict() for _, row in contacts.iterrows()],
    })
    env.filters.update({
        'update': lambda x, y: {**x, **y},
        'uuid5': lambda x, namespace: str(uuid.uuid5(uuid.UUID(namespace), x)),
        'to_json': lambda x: json.dumps(x, separators=(',', ':')),
        'to_base64': lambda x: base64.b64encode(x.encode()).decode(),
        'dump_txt': lambda x: base64.b64encode(x.encode()).decode() + '.plain.txt',
        'dump_qr': lambda x: (
            qr_img := qrcode.make(x),
            qr_img_bytes_io := io.BytesIO(),
            qr_img.save(qr_img_bytes_io, format='PNG'),
            base64.b64encode(qr_img_bytes_io.getvalue()
                             ).decode() + '.image.png',
        )[-1],
    })
    env.filters['txt_file'] = lambda x: env.filters['to_base64'](
        x) + '.plain.txt'
    return env


def run_render(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contacts = load_contacts(args)
    env = create_env(args, config, contacts)
    template = env.get_template(args.template)
    print(template.render())


def run_send(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contacts = load_contacts(args)
    env = create_env(args, config, contacts)
    txt_template = env.get_template(args.template)
    email = config['smtp']
    msgs: List[EmailMessage] = []
    for _, contact in contacts.iterrows():
        txt = frontmatter.loads(txt_template.render(contact.to_dict()))
        msg = EmailMessage()
        msg.set_charset('utf-8')
        msg['Subject'] = txt['subject']
        msg['From'] = Address(email['name'], *email['user'].split('@'))
        msg['To'] = (Address(contact['english_name'],
                     *contact['email'].split('@')),)
        msg.set_content(str(txt))
        print(' main:')
        print('\n'.join(map(lambda x: '  > ' + x, str(txt).split('\n'))))
        for filetype, path in txt.get('alternative', {}).items():
            subtype = filetype.strip()
            template = env.get_template(path)
            content = template.render(contact.to_dict())
            print(f'\n {filetype}:')
            print('\n'.join(map(lambda x: '  > ' + x, content.split('\n'))))
            msg.add_alternative(content, subtype=subtype)
        for meta in txt.get('attach', []):
            content, maintype, subtype = meta['content'].strip().split('.')
            content = base64.b64decode(content.encode())
            msg.add_attachment(content, maintype=maintype,
                               subtype=subtype, filename=meta['name'])
        reply = input(f'{contact.email} (y/N): ')
        if reply.lower() != 'y':
            sys.exit(1)
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
    main_parser.add_argument('--data', type=str,
                             default='data', help='additional data')
    main_parser.add_argument(
        '--email', action='append', default=[], help='filter emails')
    main_parser.add_argument(
        '--tag', action='append', default=[], help='filter tags')
    sub_parsers = main_parser.add_subparsers(
        title='command', help='available sub-commands')
    # init
    parser_init = sub_parsers.add_parser('render', help='render template')
    parser_init.add_argument(
        'template', help='the template used to render')
    parser_init.set_defaults(func=run_render)
    # send
    parser_email = sub_parsers.add_parser('send', help='send emails')
    parser_email.add_argument(
        'template', help='the template used to compose email')
    parser_email.set_defaults(func=run_send)

    args = main_parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        main_parser.print_help()


if __name__ == "__main__":
    main()

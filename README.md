## Proxy Service Management

### How to use

```bash
# install dependencies
pip install -r requirements.txt

# PLEASE EDIT configs and contacts
cp config.example.json config.json
cp contacts.example.json contacts.json

# generate uuid and write uuid to contacts
./main.py init --write_contacts

# send email using the template `templates/new` to all users
./main.py send new
```

Use can create CSV files under `data/`. These CSVs should contain an `email` column to match rows in `contacts,csv`, and they can contain extra columns, which will be available to the templates. See `update_usage.sh` for a practical example.

### Features

- Jinja2 template engine

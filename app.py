import base64
import csv
import datetime
import io
import json
import os
import time
from functools import wraps

import mistletoe
import requests
import xlsxwriter
from bs4 import BeautifulSoup
from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from itsdangerous import (
    BadData,
    SignatureExpired,
    URLSafeSerializer,
    URLSafeTimedSerializer,
)
from markupsafe import Markup
from peewee import IntegrityError, ProgrammingError
from werkzeug.security import check_password_hash, generate_password_hash

from database import Member, User, database

database.connection()
database.create_tables([User, Member], safe=True)
database.close()

app = Flask(__name__)

app.config["SECRET_KEY"] = base64.urlsafe_b64decode(
    os.environ.setdefault(
        "SECRET_KEY",
        base64.urlsafe_b64encode(os.urandom(24)).decode(),
    )
)

app.config["CLUB_SHORT_NAME"] = os.getenv("CLUB_SHORT_NAME")
app.config["CLUB_DISPLAY_NAME"] = os.getenv("CLUB_DISPLAY_NAME")
app.config["MAILGUN_DOMAIN"] = os.getenv("MAILGUN_DOMAIN")
app.config["MAILGUN_KEY"] = os.getenv("MAILGUN_KEY")
app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "false").lower() == "true"
app.config["APP_URL"] = os.getenv("APP_URL")
app.config["PERMANENT_SESSION_LIFETIME"] = 7257600


def normalize_query(input_query):
    tokens = input_query.split(" ")
    output_tokens = []
    for token in tokens:
        if token.isupper():
            output_tokens.append(token)
        else:
            output_tokens.append(token.lower())
    return " ".join(output_tokens)


@app.before_request
def before_request():
    g.database = database
    g.database.connection()


@app.after_request
def after_request(request):
    g.database.close()
    return request


def gen_ro_token():
    """Return only the token (slug) portion of the ro link."""
    return URLSafeTimedSerializer(app.config.get("SECRET_KEY"), salt="RO_TOKEN").dumps(
        None
    )


def check_ro_token(token):
    try:
        URLSafeTimedSerializer(app.config.get("SECRET_KEY"), salt="RO_TOKEN").loads(
            token, max_age=180 * 24 * 60 * 60
        )
    except SignatureExpired:
        raise
    except BadData:
        data = URLSafeSerializer(app.config.get("SECRET_KEY")).loads(token)

        if data.get("readonly") and data.get("time") + 7257600 >= int(time.time()):
            return

        raise SignatureExpired("Legacy token expired.")


def send_login_email(email):
    ro_url = "{0}/ro/{1}".format(app.config.get("APP_URL"), gen_ro_token())
    email_subject = f"{app.config['CLUB_DISPLAY_NAME']} Roster Access Link"
    email_body = '<a href="{0}">Click here to access the roster.</a>'
    email_body = email_body.format(ro_url)

    email_data = {
        "from": "{0} <{1}@{2}>".format(
            f"{app.config['CLUB_DISPLAY_NAME']} Roster",
            "roster",
            app.config.get("MAILGUN_DOMAIN"),
        ),
        "to": email,
        "subject": email_subject,
        "html": render_template(
            "email_layout.html",
            body=Markup(email_body),
            subject=email_subject,
        ),
    }

    requests.post(
        "https://api.mailgun.net/v3/{}/messages".format(
            app.config.get("MAILGUN_DOMAIN")
        ),
        auth=("api", app.config.get("MAILGUN_KEY")),
        data=email_data,
    )


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("appuser"):
            return f(*args, **kwargs)
        else:
            flash("You are not logged in.")
            return redirect(url_for("login"))

    return wrapper


def ro_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("readonly") and request.method == "GET":
            return f(*args, **kwargs)
        elif session.get("appuser"):
            return f(*args, **kwargs)
        else:
            flash("You are not logged in.")
            return redirect(url_for("login"))

    return wrapper


@app.route("/")
@ro_required
def index():
    records = Member.active()
    return render_template("records_table.html", records=records)


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if User.select().count() == 0:
        if request.method == "POST":
            User.create(
                username=request.form["appuser"].strip(),
                password=generate_password_hash(
                    request.form["password"],
                    method="pbkdf2:sha256",
                ),
            )
            flash("Admin user created.")
            return redirect(url_for("login"))
        else:
            flash("Create the first user.")
            return render_template("setup.html")
    else:
        flash("Admin user already exists.")
        return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            user = User.get(User.username == request.form["appuser"])
        except User.DoesNotExist:
            flash("Incorrect username or password.")
            return redirect(url_for("login"))
        if check_password_hash(user.password, request.form["password"]):
            session["appuser"] = user.username
            session.permanent = True
            flash("You are now logged in.")
            return redirect(url_for("index"))
        else:
            flash("Incorrect username or password.")
            return redirect(url_for("login"))
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


@app.route("/new-user", methods=["GET", "POST"])
@login_required
def new_user():
    if request.method == "POST":
        try:
            User.create(
                username=request.form["appuser"].strip(),
                password=generate_password_hash(
                    request.form["password"],
                    method="pbkdf2:sha256",
                ),
            )
        except IntegrityError:
            flash("That username is already taken.")
            return redirect(url_for("new_user"))
        flash("New user created.")
        return redirect(url_for("index"))
    else:
        flash("Add a new user.")
        return render_template("new_user.html")


@app.route("/search")
@ro_required
def search():
    try:
        records = list(
            Member.raw(
                "select * from member where search_content @@ %s",
                normalize_query(request.args.get("query")),
            )
        )
    except ProgrammingError:
        flash("There was an error in your search query.")
        return redirect(url_for("index"))
    flash("{} records found.".format(len(records)))
    return render_template("records.html", records=records)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        form_data = {k: v.strip() for k, v in request.form.items()}
        form_data["email"] = form_data.get("email").casefold()
        try:
            member = Member.create(**form_data)
        except IntegrityError:
            flash("Could not add record. Email address already exists.")
            return redirect(url_for("index"))
        member.update_search_content()
        flash("Record added.")
        return render_template("records.html", records=[member])
    else:
        end_of_year = (
            datetime.date.today()
            .replace(
                month=12,
                day=31,
            )
            .isoformat()
        )
        return render_template("add.html", expire=end_of_year)


@app.route("/member/<member_id>")
@ro_required
def get_member(member_id):
    member = Member.get(Member.id == member_id)
    return render_template("records.html", records=[member])


@app.route("/bulk-edit-expiry", methods=["GET", "POST"])
@login_required
def bulk_edit_expiry():
    if request.method == "POST":
        try:
            expiry_date = datetime.datetime.strptime(
                request.form["expiry_date"],
                "%Y-%m-%d",
            ).date()
        except ValueError:
            flash("Invalid date format.")
            return redirect(url_for("bulk_edit_expiry"))
        member_ids = request.form.getlist("member_id")
        if not member_ids:
            flash("No members selected.")
            return redirect(url_for("bulk_edit_expiry"))
        for member_id in member_ids:
            try:
                member = Member.get(Member.id == member_id)
                member.expire = expiry_date
                member.save()
            except Member.DoesNotExist:
                flash(f"Could not find member id: {member_id}")
        flash("Member expiry dates updated.")
        return redirect(url_for("index"))
    else:
        members = (
            Member.select()
            .order_by(
                Member.last_name,
                Member.first_name,
            )
            .dicts()
        )
        date = datetime.date.today().replace(month=12, day=31).isoformat()
        return render_template(
            "bulk_edit_expiry.html",
            members=members,
            date=date,
        )


@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    if request.method == "POST":
        form_data = {k: v.strip() for k, v in request.form.items()}
        form_data["email"] = form_data.get("email").casefold()
        try:
            Member.update(**form_data).where(Member.id == request.form["id"]).execute()
        except IntegrityError:
            flash("Could not update record. Email address already exists.")
            return redirect(url_for("index"))
        Member.get(Member.id == request.form["id"]).update_search_content()
        flash("Record updated.")
        return redirect(url_for("get_member", member_id=request.form["id"]))
    else:
        member_id = request.args.get("id")
        member = Member.get(Member.id == member_id)
        if member:
            return render_template("edit.html", record=member)
        else:
            flash("Record not found.")
            return redirect(url_for("index"))


@app.route("/delete", methods=["GET", "POST"])
@login_required
def delete():
    if request.method == "POST":
        member_id = request.form["id"]
        member = Member.get(Member.id == member_id)
        member.delete_instance(recursive=True)
        flash("Record deleted.")
        return render_template("records.html", records=[member])
    else:
        member_id = request.args.get("id")
        member = Member.get(Member.id == member_id)
        if member:
            flash("Are you sure you want to delete this record?")
            return render_template(
                "confirm_delete.html",
                records=[member],
                id=member_id,
            )
        else:
            flash("Record not found.")
            return redirect(url_for("index"))


@app.route("/all", defaults={"args": ""})
@app.route("/all/<path:args>")
@ro_required
def list_members(args):
    args = args.split("/")

    if "expired" in args:
        records = Member.expired().dicts()
    elif "current" in args:
        records = Member.current().dicts()
    elif "previous" in args:
        records = Member.previous().dicts()
    elif "active" in args:
        records = Member.active().dicts()
    else:
        records = Member.ordered().dicts()

    if "email" in args:
        emails = (
            "\n".join(record.get("email") for record in records if record.get("email"))
            + "\n"
        )
        flash("{} records found.".format(len(records)))
        return render_template("text.html", content=emails)
    elif "csv" in args:
        exclude_fields = ("search_content",)
        csv_data = io.StringIO()
        writer = csv.DictWriter(
            csv_data,
            fieldnames=list(
                field
                for field in Member._meta.sorted_field_names
                if field not in exclude_fields
            ),
        )
        writer.writeheader()
        for record in records:
            for field in exclude_fields:
                del record[field]
            writer.writerow(record)
        flash("{} records found.".format(len(records)))
        return render_template("text.html", content=csv_data.getvalue())
    elif "xlsx" in args:
        records = [
            dict(
                record,
                expire=str(record.get("expire")),
                dob=str(record.get("dob")),
            )
            for record in records
        ]
        col_names = [
            ("first_name", "First"),
            ("last_name", "Last"),
            ("ama", "AMA"),
            ("phone", "Phone"),
            ("address", "Address"),
            ("city", "City"),
            ("state", "State"),
            ("zip_code", "ZIP"),
            ("email", "E-mail"),
            ("expire", "Expiration"),
            ("dob", "Date of Birth"),
        ]
        xlsx_data = io.BytesIO()
        workbook = xlsxwriter.Workbook(xlsx_data)
        worksheet = workbook.add_worksheet("Members")
        worksheet.set_landscape()
        header = workbook.add_format({"bold": True, "bottom": True})
        gray_bg = workbook.add_format({"bg_color": "#DDDDDD"})
        for col, name in enumerate(col_names):
            worksheet.write(0, col, name[1], header)
        for row, record in enumerate(records, start=1):
            for col, field in enumerate(col_names):
                worksheet.write(row, col, record.get(field[0]))
        for row in range(2, len(records) + 1, 2):
            worksheet.set_row(row, None, gray_bg)
        worksheet.merge_range(
            len(records) + 2,
            0,
            len(records) + 2,
            len(col_names) - 1,
            "{} members".format(len(records)),
        )
        worksheet.merge_range(
            len(records) + 3,
            0,
            len(records) + 3,
            len(col_names) - 1,
            "Generated: {}".format(datetime.date.today().isoformat()),
        )
        worksheet.print_area(0, 0, len(records) + 3, len(col_names) - 1)
        worksheet.fit_to_pages(1, 1)
        workbook.close()
        xlsx_data.seek(0)
        return send_file(
            xlsx_data,
            as_attachment=True,
            download_name="{}-roster-{}.xlsx".format(
                app.config["CLUB_SHORT_NAME"],
                datetime.date.today().isoformat(),
            ),
        )
    else:
        flash("{} records found.".format(len(records)))
        return render_template("records_table.html", records=records)


@app.route("/export")
@ro_required
def json_export():
    return jsonify(
        members=[
            dict(member, expire=str(member["expire"]))
            for member in Member.select().dicts()
        ]
    )


@app.route("/import", methods=["GET", "POST"])
@login_required
def json_import():
    if request.method == "POST":
        json_data = request.form["json_data"]
        records = json.loads(json_data).get("members")
        with database.atomic():
            if Member.insert_many(records).execute():
                for member in Member.select():
                    member.update_search_content()
                flash("Records imported.")
            else:
                flash("There was an error importing the records.")
        return redirect(url_for("index"))
    else:
        return render_template("import.html")


@app.route("/verify")
@ro_required
def verify():
    record = Member.get(Member.id == request.args.get("id"))
    res = requests.post(
        "https://www.modelaircraft.org/membership/verify",
        params={"ajax_form": "1"},
        data={
            "form_id": "membership_verify_form",
            "last_name": record.last_name,
            "ama_number": record.ama,
        },
    )
    soup = BeautifulSoup(json.loads(res.text)[0]["data"], "html.parser")
    ama_status = [
        stripped_line
        for stripped_line in (line.strip() for line in soup.text.split("\n"))
        if stripped_line
    ][1]
    return render_template(
        "records.html",
        ama_status=ama_status,
        records=[record],
    )


@app.route("/send", methods=["GET", "POST"])
@login_required
def send_email():
    if request.method == "POST":
        if "confirm-send" in request.form:
            s = URLSafeSerializer(app.config.get("SECRET_KEY"), salt="SEND_EMAIL_DATA")
            try:
                email_data = s.loads(request.form.get("email_data"))
            except Exception:
                flash("Error decoding email data.")
                return redirect(url_for("send_email"))
            mailgun_response = requests.post(
                "https://api.mailgun.net/v3/{}/messages".format(
                    app.config.get("MAILGUN_DOMAIN")
                ),
                auth=("api", app.config.get("MAILGUN_KEY")),
                data=email_data,
            )
            flash("Response from mailgun: {}".format(mailgun_response.text))
            return redirect(url_for("index"))
        if "send-active" in request.form:
            members = Member.active().dicts()
        elif "send-current" in request.form:
            members = Member.current().dicts()
        elif "send-previous" in request.form:
            members = Member.previous().dicts()
        elif "send-custom" in request.form:
            members = json.loads(request.form.get("custom-list"))
        elif "send-test" in request.form:
            members = [
                {
                    "first_name": request.form.get("test-first"),
                    "last_name": request.form.get("test-last"),
                    "email": request.form.get("test-email"),
                }
            ]
        else:
            flash("Missing form field. Please report this error.")
            return redirect(url_for("index"))
        recipient_variables = {}
        for member in members:
            if member.get("email"):
                recipient_variables[member.get("email")] = {}
                recipient_variables[member.get("email")]["name"] = "{0} {1}".format(
                    member.get("first_name", "Hello"), member.get("last_name", "")
                ).strip()
                recipient_variables[member.get("email")]["id"] = member.get("id")
        email_data = {
            "from": "{0} <{1}@{2}>".format(
                request.form.get("from-name"),
                request.form.get("from-email"),
                app.config.get("MAILGUN_DOMAIN"),
            ),
            "to": [email for email in recipient_variables.keys()],
            "subject": request.form.get("subject"),
            "text": request.form.get("body"),
            "html": render_template(
                "email_layout.html",
                body=Markup(mistletoe.markdown(request.form.get("body"))),
                subject=request.form.get("subject"),
            ),
            "recipient-variables": json.dumps(recipient_variables),
        }
        s = URLSafeSerializer(app.config.get("SECRET_KEY"), salt="SEND_EMAIL_DATA")
        return render_template(
            "send_email_confirm.html",
            num_recipients=len(email_data["to"]),
            email_body=Markup(
                mistletoe.markdown(
                    request.form.get("body").replace("%recipient.name%", "John Doe")
                )
            ),
            email_data=email_data,
            email_data_json=s.dumps(email_data),
        )
    else:
        ro_url = "{0}{1}".format(
            app.config.get("APP_URL"), url_for("ro_auth", slug=gen_ro_token())
        )
        return render_template(
            "send_email.html",
            month=datetime.date.today().strftime("%B"),
            domain=app.config.get("MAILGUN_DOMAIN"),
            ro_url=ro_url,
        )


@app.route("/get-ro-token")
@login_required
def get_ro_token():
    return render_template("get_ro_token.html", slug=gen_ro_token())


@app.route("/ro/<slug>")
def ro_auth(slug):
    try:
        check_ro_token(slug)
    except BadData:
        flash("Authorization failed.")
        return redirect(url_for("index"))

    session["readonly"] = True
    session.permanent = True
    flash("You have read only access.")
    return render_template("ro_authorized.html")


@app.route("/email-login", methods=["POST"])
def email_login():
    email = request.form.get("email")
    if len(email) >= 3:
        try:
            member = Member.get(Member.email == email.casefold())
            send_login_email(member.email)
            flash("Login email has been sent. Please check your email.")
        except Member.DoesNotExist:
            flash("Email address not found.")
    else:
        flash("Invalid email address.")
    return redirect(url_for("login"))


@app.route("/about")
def about():
    with open("version") as f:
        version = f.read()
    version = version.strip()[:8]
    return render_template("about.html", version=version)


if __name__ == "__main__":
    app.run(host="0.0.0.0")

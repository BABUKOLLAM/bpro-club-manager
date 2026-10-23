"""Server-side texts: the messages that go out by WhatsApp, SMS, e-mail and in-app notification, in English and Malayalam.

Each template has a short `subject` (used as e-mail subject / notification title) and a `body`. `{placeholders}` are
filled from the context the caller passes. SMS bodies are kept short on purpose: Malayalam SMS is Unicode and costs
70 characters per segment.
"""

TEMPLATES = {
    "application_received": {
        "en": ("Application received", "Dear {name}, your membership application to {club} has been received. "
               "We will inform you once the committee approves it. - {club_short}"),
        "ml": ("അപേക്ഷ ലഭിച്ചു", "പ്രിയ {name}, {club} അംഗത്വത്തിനുള്ള താങ്കളുടെ അപേക്ഷ ലഭിച്ചു. "
               "കമ്മിറ്റി അംഗീകരിച്ചാലുടൻ അറിയിക്കുന്നതാണ്. - {club_short}"),
    },
    "application_approved": {
        "en": ("Welcome to {club_short}", "Dear {name}, your membership is approved. Membership No: {member_no}. "
               "Sign in at {link} with your phone/e-mail to update your family details and receive club news. - {club}"),
        "ml": ("{club_short}-ലേക്ക് സ്വാഗതം", "പ്രിയ {name}, താങ്കളുടെ അംഗത്വം അംഗീകരിച്ചു. അംഗത്വ നമ്പർ: {member_no}. "
               "കുടുംബവിവരങ്ങൾ പുതുക്കാനും ക്ലബ്ബ് വാർത്തകൾ ലഭിക്കാനും {link} എന്നതിൽ പ്രവേശിക്കുക. - {club}"),
    },
    "application_rejected": {
        "en": ("Membership application", "Dear {name}, we are sorry - your membership application could not be accepted at this time. {note} - {club}"),
        "ml": ("അംഗത്വ അപേക്ഷ", "പ്രിയ {name}, ക്ഷമിക്കണം - താങ്കളുടെ അംഗത്വ അപേക്ഷ ഇപ്പോൾ സ്വീകരിക്കാനായില്ല. {note} - {club}"),
    },
    "news": {
        "en": ("{title}", "{club_short} News: {title}\n{summary}\n{link}"),
        "ml": ("{title}", "{club_short} വാർത്ത: {title}\n{summary}\n{link}"),
    },
    "event": {
        "en": ("{title}", "{club_short} {kind_label}: {title}\nWhen: {when}\nWhere: {venue}\n{summary}\n{link}"),
        "ml": ("{title}", "{club_short} {kind_label}: {title}\nതീയതി: {when}\nസ്ഥലം: {venue}\n{summary}\n{link}"),
    },
    "event_reminder": {
        "en": ("Reminder: {title}", "Reminder from {club_short}: {title} is on {when} at {venue}. {link}"),
        "ml": ("ഓർമ്മപ്പെടുത്തൽ: {title}", "{club_short} ഓർമ്മപ്പെടുത്തൽ: {title} - {when}, {venue}. {link}"),
    },
    "registration_confirmed": {
        "en": ("Registered: {title}", "Dear {name}, {participant} is registered for {title} ({item}). {when}, {venue}. - {club_short}"),
        "ml": ("രജിസ്റ്റർ ചെയ്തു: {title}", "പ്രിയ {name}, {participant} {title} ({item}) -ൽ രജിസ്റ്റർ ചെയ്തു. {when}, {venue}. - {club_short}"),
    },
    "results": {
        "en": ("Results: {title}", "{club_short}: results of {title} are published. {link}"),
        "ml": ("ഫലം: {title}", "{club_short}: {title} -ന്റെ ഫലങ്ങൾ പ്രസിദ്ധീകരിച്ചു. {link}"),
    },
    "meeting_notice": {
        "en": ("Meeting: {title}", "{committee} meeting notice\n{title}\nDate: {when}\nVenue: {venue}\nAgenda:\n{agenda}\nKindly attend. - {convener}"),
        "ml": ("യോഗം: {title}", "{committee} യോഗ അറിയിപ്പ്\n{title}\nതീയതി: {when}\nസ്ഥലം: {venue}\nഅജണ്ട:\n{agenda}\nദയവായി പങ്കെടുക്കുക. - {convener}"),
    },
    "mom_published": {
        "en": ("Minutes: {title}", "Minutes of {committee} meeting held on {when} are published. {link}"),
        "ml": ("മിനിറ്റ്സ്: {title}", "{when}-ന് നടന്ന {committee} യോഗത്തിന്റെ മിനിറ്റ്സ് പ്രസിദ്ധീകരിച്ചു. {link}"),
    },
    "action_assigned": {
        "en": ("Action: {title}", "Dear {name}, you are responsible for: {title}. Due: {due}. ({committee}) {link}"),
        "ml": ("ചുമതല: {title}", "പ്രിയ {name}, താങ്കൾക്ക് ചുമതല: {title}. അവസാന തീയതി: {due}. ({committee}) {link}"),
    },
    "book_issued": {
        "en": ("Book issued", "Dear {name}, '{book}' (Acc. {acc}) is issued to you. Please return by {due}. - {club_short} Library"),
        "ml": ("പുസ്തകം നൽകി", "പ്രിയ {name}, '{book}' (Acc. {acc}) താങ്കൾക്ക് നൽകി. {due}-നകം തിരികെ നൽകുക. - {club_short} ലൈബ്രറി"),
    },
    "book_due": {
        "en": ("Book due", "Dear {name}, '{book}' is due on {due}. Please return or renew. - {club_short} Library"),
        "ml": ("പുസ്തകം തിരികെ നൽകേണ്ട തീയതി", "പ്രിയ {name}, '{book}' {due}-ന് തിരികെ നൽകേണ്ടതാണ്. - {club_short} ലൈബ്രറി"),
    },
    "book_overdue": {
        "en": ("Book overdue", "Dear {name}, '{book}' was due on {due} ({days} days ago). Fine so far: Rs {fine}. Please return it. - {club_short} Library"),
        "ml": ("പുസ്തകം കാലാവധി കഴിഞ്ഞു", "പ്രിയ {name}, '{book}' {due}-ന് തിരികെ നൽകേണ്ടതായിരുന്നു ({days} ദിവസം കഴിഞ്ഞു). പിഴ: Rs {fine}. ദയവായി തിരികെ നൽകുക. - {club_short} ലൈബ്രറി"),
    },
    "reservation_ready": {
        "en": ("Book available", "Dear {name}, '{book}' you reserved is now available. Please collect within 3 days. - {club_short} Library"),
        "ml": ("പുസ്തകം ലഭ്യമാണ്", "പ്രിയ {name}, താങ്കൾ റിസർവ് ചെയ്ത '{book}' ഇപ്പോൾ ലഭ്യമാണ്. 3 ദിവസത്തിനകം വാങ്ങുക. - {club_short} ലൈബ്രറി"),
    },
    "receipt": {
        "en": ("Receipt {no}", "Dear {name}, received Rs {amount} towards {head} on {date}. Receipt No {no}. Thank you. - {club}"),
        "ml": ("രസീത് {no}", "പ്രിയ {name}, {date}-ന് {head} ഇനത്തിൽ Rs {amount} ലഭിച്ചു. രസീത് നമ്പർ {no}. നന്ദി. - {club}"),
    },
    "subscription_due": {
        "en": ("Subscription due", "Dear {name}, your {year} annual subscription of Rs {amount} is due. Kindly pay at the club office. - {club_short}"),
        "ml": ("വരിസംഖ്യ അടയ്ക്കാനുണ്ട്", "പ്രിയ {name}, {year} വർഷത്തെ വാർഷിക വരിസംഖ്യ Rs {amount} അടയ്ക്കാനുണ്ട്. ക്ലബ്ബ് ഓഫീസിൽ അടയ്ക്കുക. - {club_short}"),
    },
    "birthday": {
        "en": ("Happy birthday", "Dear {name}, warm birthday wishes from all of us at {club}!"),
        "ml": ("ജന്മദിനാശംസകൾ", "പ്രിയ {name}, {club} -ലെ ഞങ്ങളുടെ എല്ലാവരുടെയും ഹൃദയം നിറഞ്ഞ ജന്മദിനാശംസകൾ!"),
    },
    "saas_ending": {
        "en": ("{product}: subscription ends in {days} days", "Your club's {product} subscription ends in {days} days. {members} active members · ₹{price} for the next year. "
               "Pay online or by UPI at {link} to keep everything running. {support}"),
        "ml": ("{product}: സബ്സ്ക്രിപ്ഷൻ {days} ദിവസത്തിനുള്ളിൽ അവസാനിക്കും", "നിങ്ങളുടെ ക്ലബ്ബിന്റെ {product} സബ്സ്ക്രിപ്ഷൻ {days} ദിവസത്തിനുള്ളിൽ അവസാനിക്കും. "
               "{members} സജീവ അംഗങ്ങൾ · അടുത്ത വർഷത്തേക്ക് ₹{price}. {link} -ൽ ഓൺലൈനായോ UPI വഴിയോ അടയ്ക്കുക. {support}"),
    },
    "saas_overdue": {
        "en": ("{product}: payment due", "Your club's {product} subscription has ended. Pay ₹{price} within {grace} days at {link}; after that the club becomes read-only until paid. {support}"),
        "ml": ("{product}: പണമടയ്ക്കാനുണ്ട്", "നിങ്ങളുടെ ക്ലബ്ബിന്റെ {product} സബ്സ്ക്രിപ്ഷൻ അവസാനിച്ചു. {grace} ദിവസത്തിനുള്ളിൽ {link} -ൽ ₹{price} അടയ്ക്കുക; "
               "അതിനുശേഷം പണമടയ്ക്കുന്നതുവരെ ക്ലബ്ബ് വായിക്കാൻ മാത്രമാകും. {support}"),
    },
    "saas_suspended": {
        "en": ("{product}: club is read-only", "Your club's {product} subscription is unpaid, so the club is now read-only. Nothing is deleted. Pay ₹{price} at {link} to reopen it. {support}"),
        "ml": ("{product}: ക്ലബ്ബ് വായിക്കാൻ മാത്രം", "നിങ്ങളുടെ ക്ലബ്ബിന്റെ {product} സബ്സ്ക്രിപ്ഷൻ അടച്ചിട്ടില്ലാത്തതിനാൽ ക്ലബ്ബ് ഇപ്പോൾ വായിക്കാൻ മാത്രം. ഒന്നും നഷ്ടപ്പെട്ടിട്ടില്ല. "
               "{link} -ൽ ₹{price} അടച്ചാൽ വീണ്ടും തുറക്കും. {support}"),
    },
    "broadcast": {
        "en": ("{subject}", "{body}"),
        "ml": ("{subject}", "{body}"),
    },
    "payment_claimed": {
        "en": ("Payment received for checking", "Dear {name}, we have noted your UPI payment of Rs {amount} (ref {utr}). The treasurer will confirm it and you will get the receipt. - {club_short}"),
        "ml": ("പണമടച്ചതായി രേഖപ്പെടുത്തി", "പ്രിയ {name}, താങ്കളുടെ UPI പേയ്മെന്റ് Rs {amount} (ref {utr}) രേഖപ്പെടുത്തി. ട്രഷറർ സ്ഥിരീകരിച്ചാൽ രസീത് ലഭിക്കും. - {club_short}"),
    },
    "payment_rejected": {
        "en": ("Payment not matched", "Dear {name}, we could not match your UPI payment claim of Rs {amount} (ref {utr}). {note} Please contact the treasurer. - {club_short}"),
        "ml": ("പേയ്മെന്റ് സ്ഥിരീകരിക്കാനായില്ല", "പ്രിയ {name}, താങ്കളുടെ UPI പേയ്മെന്റ് Rs {amount} (ref {utr}) സ്ഥിരീകരിക്കാനായില്ല. {note} ട്രഷററെ ബന്ധപ്പെടുക. - {club_short}"),
    },
    "booking_confirmed": {
        "en": ("Booking confirmed: {facility}", "Dear {name}, your booking of {facility} from {starts} to {ends} is confirmed. Amount: Rs {amount}. - {club_short}"),
        "ml": ("ബുക്കിംഗ് സ്ഥിരീകരിച്ചു: {facility}", "പ്രിയ {name}, {facility} {starts} മുതൽ {ends} വരെ ബുക്കിംഗ് സ്ഥിരീകരിച്ചു. തുക: Rs {amount}. - {club_short}"),
    },
    "booking_cancelled": {
        "en": ("Booking cancelled: {facility}", "Dear {name}, your booking of {facility} on {starts} is cancelled. {note} - {club_short}"),
        "ml": ("ബുക്കിംഗ് റദ്ദാക്കി: {facility}", "പ്രിയ {name}, {starts}-ലെ {facility} ബുക്കിംഗ് റദ്ദാക്കി. {note} - {club_short}"),
    },
    "asset_due": {
        "en": ("Return: {asset}", "Dear {name}, please return {asset} ({qty}) borrowed on {lent}. Due {due}. - {club_short}"),
        "ml": ("തിരികെ നൽകുക: {asset}", "പ്രിയ {name}, {lent}-ന് വാങ്ങിയ {asset} ({qty}) {due}-നകം തിരികെ നൽകുക. - {club_short}"),
    },
    "blood_request": {
        "en": ("Urgent: {blood} blood needed", "URGENT: {blood} blood is needed for {patient} at {hospital}. {detail} Please contact {contact}. - {club_short}"),
        "ml": ("അടിയന്തരം: {blood} രക്തം ആവശ്യമുണ്ട്", "അടിയന്തരം: {hospital}-ൽ {patient}-ന് {blood} രക്തം ആവശ്യമുണ്ട്. {detail} ദയവായി {contact}-ൽ ബന്ധപ്പെടുക. - {club_short}"),
    },
    "payment_success": {
        "en": ("Payment received", "Dear {name}, your online payment of Rs {amount} ({payment_id}) is received. Receipt No {no}. Thank you. - {club}"),
        "ml": ("പണം ലഭിച്ചു", "പ്രിയ {name}, താങ്കളുടെ ഓൺലൈൻ പേയ്മെന്റ് Rs {amount} ({payment_id}) ലഭിച്ചു. രസീത് നമ്പർ {no}. നന്ദി. - {club}"),
    },
    "poll_open": {
        "en": ("{kind}: {title}", "{club_short} {kind} is open: {title}. Please cast your vote before {ends}. {link}"),
        "ml": ("{kind}: {title}", "{club_short} {kind} തുടങ്ങി: {title}. {ends}-ന് മുമ്പ് വോട്ട് ചെയ്യുക. {link}"),
    },
    "poll_results": {
        "en": ("Results: {title}", "{club_short}: results of '{title}' are out. {summary} {link}"),
        "ml": ("ഫലം: {title}", "{club_short}: '{title}' ഫലം പ്രസിദ്ധീകരിച്ചു. {summary} {link}"),
    },
    "password_reset": {
        "en": ("Sign-in code", "{club_short}: your one-time sign-in code is {code}. Valid for 10 minutes."),
        "ml": ("പ്രവേശന കോഡ്", "{club_short}: താങ്കളുടെ ഒറ്റത്തവണ പ്രവേശന കോഡ് {code}. 10 മിനിറ്റ് സാധുത."),
    },
}

POLL_KIND_LABELS = {"poll": {"en": "Poll", "ml": "അഭിപ്രായ വോട്ടെടുപ്പ്"}, "election": {"en": "Election", "ml": "തിരഞ്ഞെടുപ്പ്"}}
KIND_LABELS = {
    "news": {"en": "News", "ml": "വാർത്ത"},
    "event": {"en": "Event", "ml": "പരിപാടി"},
    "camp": {"en": "Camp", "ml": "ക്യാമ്പ്"},
    "competition": {"en": "Competition", "ml": "മത്സരം"},
    "activity": {"en": "Social activity", "ml": "സാമൂഹിക പ്രവർത്തനം"},
    "notice": {"en": "Notice", "ml": "അറിയിപ്പ്"},
}

HEAD_LABELS = {
    "admission": {"en": "Admission fee", "ml": "പ്രവേശന ഫീസ്"},
    "subscription": {"en": "Annual subscription", "ml": "വാർഷിക വരിസംഖ്യ"},
    "donation": {"en": "Donation", "ml": "സംഭാവന"},
    "event_fee": {"en": "Event fee", "ml": "പരിപാടി ഫീസ്"},
    "library_fine": {"en": "Library fine", "ml": "ലൈബ്രറി പിഴ"},
    "library_deposit": {"en": "Library deposit", "ml": "ലൈബ്രറി നിക്ഷേപം"},
    "sponsorship": {"en": "Sponsorship", "ml": "സ്പോൺസർഷിപ്പ്"},
    "grant": {"en": "Grant", "ml": "ഗ്രാന്റ്"},
    "other_income": {"en": "Other income", "ml": "മറ്റ് വരുമാനം"},
    "event_expense": {"en": "Event expense", "ml": "പരിപാടി ചെലവ്"},
    "books": {"en": "Books & periodicals", "ml": "പുസ്തകങ്ങൾ & ആനുകാലികങ്ങൾ"},
    "rent": {"en": "Rent & utilities", "ml": "വാടക & യൂട്ടിലിറ്റി"},
    "salary": {"en": "Salary & honorarium", "ml": "ശമ്പളം & ഓണറേറിയം"},
    "maintenance": {"en": "Maintenance", "ml": "അറ്റകുറ്റപ്പണി"},
    "charity": {"en": "Charity & welfare", "ml": "ജീവകാരുണ്യം & ക്ഷേമം"},
    "other_expense": {"en": "Other expense", "ml": "മറ്റ് ചെലവ്"},
}
RECEIPT_HEADS = ["admission", "subscription", "donation", "event_fee", "library_fine", "library_deposit", "sponsorship", "grant", "other_income"]
PAYMENT_HEADS = ["event_expense", "books", "rent", "salary", "maintenance", "charity", "other_expense"]


class _Safe(dict):
    def __missing__(self, k):
        return ""


def render(key, lang, ctx):
    lang = lang if lang in ("en", "ml") else "en"
    subject, body = TEMPLATES[key][lang]
    safe = _Safe(ctx)
    return subject.format_map(safe).strip(), body.format_map(safe).strip()


def label(table, key, lang):
    item = table.get(key)
    if not item:
        return key
    return item.get(lang) or item.get("en") or key


def pick(row, field, lang):
    """Bilingual field: the requested language, falling back to the other."""
    a = row.get(f"{field}_{lang}") or ""
    b = row.get(f"{field}_{'en' if lang == 'ml' else 'ml'}") or ""
    return a or b

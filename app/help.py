"""The handbook: how to use the app, for members and for office bearers, in English and Malayalam, served at /help
(printable) and as JSON for the in-app help screen. Content lives here so it ships with the code it describes."""
import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import db

router = APIRouter()

# Each section: key, audience ('member' | 'office'), title (en, ml), paragraphs [(en, ml), ...]. Steps are plain sentences.
SECTIONS = [
    ("start", "member", ("Getting started", "തുടങ്ങാം"), [
        ("Open the club's web address on your phone. Tap your browser's menu and choose 'Add to Home screen' to install it like an app; it then opens full-screen and can send you notifications.",
         "ക്ലബ്ബിന്റെ വെബ് വിലാസം ഫോണിൽ തുറക്കുക. ബ്രൗസർ മെനുവിൽ 'Add to Home screen' തിരഞ്ഞെടുത്താൽ ആപ്പ് പോലെ ഇൻസ്റ്റാൾ ആകും; പിന്നെ ഫുൾ സ്ക്രീനിൽ തുറക്കും, അറിയിപ്പുകളും ലഭിക്കും."),
        ("Switch between English and Malayalam with the language button at the top. Every screen and every message the club sends comes in the language you choose.",
         "മുകളിലെ ഭാഷാ ബട്ടൺ കൊണ്ട് ഇംഗ്ലീഷും മലയാളവും മാറ്റാം. എല്ലാ സ്ക്രീനും ക്ലബ്ബ് അയയ്ക്കുന്ന എല്ലാ സന്ദേശവും താങ്കൾ തിരഞ്ഞെടുത്ത ഭാഷയിൽ ലഭിക്കും."),
    ]),
    ("apply", "member", ("Applying for membership", "അംഗത്വത്തിന് അപേക്ഷിക്കൽ"), [
        ("Tap 'Apply for membership' on the front page. The form takes you step by step: your details, contact and address, family members, a photo (take a selfie or choose one from the gallery), and a password.",
         "മുൻപേജിൽ 'അംഗത്വത്തിന് അപേക്ഷിക്കുക' അമർത്തുക. ഫോം ഘട്ടം ഘട്ടമായി കൊണ്ടുപോകും: താങ്കളുടെ വിവരങ്ങൾ, ഫോണും വിലാസവും, കുടുംബാംഗങ്ങൾ, ഫോട്ടോ (സെൽഫി എടുക്കുകയോ ഗാലറിയിൽ നിന്ന് തിരഞ്ഞെടുക്കുകയോ), പാസ്‌വേഡ്."),
        ("Your phone number becomes your login. After the committee approves the application you receive your membership number by WhatsApp or SMS and can sign in.",
         "ഫോൺ നമ്പറാണ് താങ്കളുടെ ലോഗിൻ. കമ്മിറ്റി അപേക്ഷ അംഗീകരിച്ചാൽ അംഗത്വ നമ്പർ വാട്സ്ആപ്പ് / SMS വഴി ലഭിക്കും; പിന്നെ പ്രവേശിക്കാം."),
        ("Forgot the password? Tap 'Forgot password?' on the sign-in page; a one-time code comes to your phone and you set a new one.",
         "പാസ്‌വേഡ് മറന്നോ? പ്രവേശന പേജിൽ 'പാസ്‌വേഡ് മറന്നോ?' അമർത്തുക; ഒറ്റത്തവണ കോഡ് ഫോണിൽ വരും, പുതിയത് സജ്ജമാക്കാം."),
    ]),
    ("profile", "member", ("Your profile, family and e-card", "പ്രൊഫൈൽ, കുടുംബം, ഇ-കാർഡ്"), [
        ("'My profile' shows your details and your electronic membership card. Save the card to your phone or share it; the QR on it is what the office scans at meetings, events and the reading room.",
         "'എന്റെ പ്രൊഫൈൽ'-ൽ താങ്കളുടെ വിവരങ്ങളും ഇലക്ട്രോണിക് അംഗത്വ കാർഡും കാണാം. കാർഡ് ഫോണിൽ സേവ് ചെയ്യാം, പങ്കുവയ്ക്കാം; യോഗങ്ങളിലും പരിപാടികളിലും വായനശാലയിലും ഓഫീസ് സ്കാൻ ചെയ്യുന്നത് അതിലെ QR ആണ്."),
        ("Under 'My family' add your spouse, children and parents with their dates of birth and blood groups. Family members can be registered for events and competitions, and the club's blood-donor search uses these blood groups.",
         "'എന്റെ കുടുംബം'-ൽ ഭാര്യ/ഭർത്താവ്, മക്കൾ, മാതാപിതാക്കൾ എന്നിവരെ ജനനത്തീയതിയും രക്തഗ്രൂപ്പും സഹിതം ചേർക്കുക. കുടുംബാംഗങ്ങളെ പരിപാടികൾക്കും മത്സരങ്ങൾക്കും രജിസ്റ്റർ ചെയ്യാം; രക്തദാതാവിനെ തിരയുമ്പോൾ ഈ രക്തഗ്രൂപ്പുകൾ ഉപയോഗിക്കും."),
        ("Under 'Notification preferences' choose whether you want WhatsApp, SMS and e-mail, whether your phone appears in the members directory, and turn on phone notifications.",
         "'അറിയിപ്പ് മുൻഗണനകൾ'-ൽ വാട്സ്ആപ്പ്, SMS, ഇ-മെയിൽ വേണോ എന്നും, ഡയറക്ടറിയിൽ ഫോൺ നമ്പർ കാണിക്കണോ എന്നും തിരഞ്ഞെടുക്കാം; ഫോൺ അറിയിപ്പുകൾ ഓൺ ചെയ്യാം."),
    ]),
    ("events", "member", ("News, events and competitions", "വാർത്തകൾ, പരിപാടികൾ, മത്സരങ്ങൾ"), [
        ("'News & events' lists everything the club publishes. Open an event to register yourself or a family member; for competitions choose the item. You get a confirmation and a reminder the day before.",
         "'വാർത്തകളും പരിപാടികളും'-ൽ ക്ലബ്ബ് പ്രസിദ്ധീകരിക്കുന്നതെല്ലാം കാണാം. ഒരു പരിപാടി തുറന്ന് താങ്കളെയോ കുടുംബാംഗത്തെയോ രജിസ്റ്റർ ചെയ്യുക; മത്സരങ്ങളിൽ ഇനം തിരഞ്ഞെടുക്കുക. സ്ഥിരീകരണവും തലേദിവസം ഓർമ്മപ്പെടുത്തലും ലഭിക്കും."),
        ("Results, fixtures and the points table appear on the same page when the office publishes them. Use 'Share' to send a public event to a WhatsApp group.",
         "ഫലങ്ങൾ, മത്സരക്രമം, പോയിന്റ് പട്ടിക എന്നിവ ഓഫീസ് പ്രസിദ്ധീകരിക്കുമ്പോൾ അതേ പേജിൽ കാണാം. പൊതു പരിപാടി വാട്സ്ആപ്പ് ഗ്രൂപ്പിലേക്ക് അയയ്ക്കാൻ 'പങ്കുവയ്ക്കുക' ഉപയോഗിക്കുക."),
    ]),
    ("library_m", "member", ("Library and reading room", "ലൈബ്രറിയും വായനശാലയും"), [
        ("Search the catalogue by title, author or accession number. If every copy is out, reserve it; you are messaged when it is back. 'My books' shows your loans and due dates and lets you renew once online.",
         "തലക്കെട്ട്, ഗ്രന്ഥകർത്താവ്, അക്സഷൻ നമ്പർ എന്നിവ കൊണ്ട് കാറ്റലോഗിൽ തിരയാം. എല്ലാ പ്രതിയും പുറത്താണെങ്കിൽ റിസർവ് ചെയ്യുക; തിരികെ വന്നാൽ സന്ദേശം ലഭിക്കും. 'എന്റെ പുസ്തകങ്ങൾ'-ൽ കൈവശമുള്ളവയും തിരികെ നൽകേണ്ട തീയതിയും കാണാം; ഒരു തവണ ഓൺലൈനായി പുതുക്കാം."),
    ]),
    ("pay", "member", ("Paying subscription and fees", "വരിസംഖ്യയും ഫീസും അടയ്ക്കൽ"), [
        ("'My payments' shows what is due and every receipt. Pay by UPI: scan the QR with any UPI app or tap Pay, then tap 'I have paid' and enter the transaction number; the treasurer confirms it and your receipt arrives. Where online payment is enabled, 'Pay online' takes card, UPI or net banking and the receipt is instant.",
         "'എന്റെ പണമിടപാടുകൾ'-ൽ അടയ്ക്കാനുള്ളതും എല്ലാ രസീതുകളും കാണാം. UPI വഴി അടയ്ക്കാം: ഏത് UPI ആപ്പിലും QR സ്കാൻ ചെയ്യുകയോ Pay അമർത്തുകയോ ചെയ്തിട്ട് 'ഞാൻ അടച്ചു' അമർത്തി ഇടപാട് നമ്പർ നൽകുക; ട്രഷറർ സ്ഥിരീകരിച്ചാൽ രസീത് വരും. ഓൺലൈൻ പേയ്മെന്റ് ഉള്ളിടത്ത് 'ഓൺലൈനായി അടയ്ക്കുക' കാർഡ്, UPI, നെറ്റ് ബാങ്കിംഗ് സ്വീകരിക്കും; രസീത് ഉടൻ ലഭിക്കും."),
    ]),
    ("more_m", "member", ("Meetings, polls, bookings, documents", "യോഗങ്ങൾ, വോട്ടെടുപ്പ്, ബുക്കിംഗ്, രേഖകൾ"), [
        ("If you are on a committee you see its meetings, the agenda and, once published, the minutes and your action items. General body meetings are visible to every member.",
         "താങ്കൾ ഒരു കമ്മിറ്റിയിലുണ്ടെങ്കിൽ അതിന്റെ യോഗങ്ങൾ, അജണ്ട, പ്രസിദ്ധീകരിച്ചാൽ മിനിറ്റ്സ്, താങ്കളുടെ ചുമതലകൾ എന്നിവ കാണാം. പൊതുയോഗങ്ങൾ എല്ലാ അംഗങ്ങൾക്കും കാണാം."),
        ("'Polls & elections' lists open votes. Each member votes once; a secret ballot never records who chose what. Results appear when voting closes.",
         "'വോട്ടെടുപ്പും തിരഞ്ഞെടുപ്പും'-ൽ നടക്കുന്ന വോട്ടെടുപ്പുകൾ കാണാം. ഓരോ അംഗത്തിനും ഒരു വോട്ട്; രഹസ്യ ബാലറ്റിൽ ആര് എന്ത് തിരഞ്ഞെടുത്തു എന്ന് രേഖപ്പെടുത്തില്ല. വോട്ടെടുപ്പ് അവസാനിച്ചാൽ ഫലം കാണാം."),
        ("'Hall & ground booking' shows the calendar; request a slot and the office confirms it. 'Documents' holds the bye-laws, circulars and minutes you are entitled to see.",
         "'ഹാൾ & ഗ്രൗണ്ട് ബുക്കിംഗ്'-ൽ കലണ്ടർ കാണാം; സമയം അഭ്യർത്ഥിച്ചാൽ ഓഫീസ് സ്ഥിരീകരിക്കും. 'രേഖകൾ'-ൽ നിയമാവലി, സർക്കുലറുകൾ, താങ്കൾക്ക് കാണാവുന്ന മിനിറ്റ്സ് എന്നിവയുണ്ട്."),
    ]),
    ("roles", "office", ("Roles", "റോളുകൾ"), [
        ("Administrator: everything, including settings and backups. President and Secretary: members, publishing, committees and minutes, broadcasts. Treasurer: accounts, dues, UPI confirmations, bookings. Librarian: the library desk and assets. A committee convener manages that committee's meetings, minutes, actions and polls without any office role.",
         "അഡ്മിനിസ്ട്രേറ്റർ: ക്രമീകരണങ്ങളും ബാക്കപ്പുകളും ഉൾപ്പെടെ എല്ലാം. പ്രസിഡന്റ്, സെക്രട്ടറി: അംഗങ്ങൾ, പ്രസിദ്ധീകരണം, കമ്മിറ്റികളും മിനിറ്റ്സും, സന്ദേശങ്ങൾ. ട്രഷറർ: കണക്കുകൾ, കുടിശ്ശിക, UPI സ്ഥിരീകരണം, ബുക്കിംഗ്. ലൈബ്രേറിയൻ: ലൈബ്രറി ഡെസ്കും ആസ്തികളും. കമ്മിറ്റി കൺവീനർക്ക് ഓഫീസ് റോളില്ലാതെ ആ കമ്മിറ്റിയുടെ യോഗങ്ങൾ, മിനിറ്റ്സ്, ചുമതലകൾ, വോട്ടെടുപ്പ് നടത്താം."),
        ("Add office users under 'Users & roles'. Link each to their member record so they also get member features.",
         "'ഉപയോക്താക്കളും റോളുകളും'-ൽ ഓഫീസ് ഉപയോക്താക്കളെ ചേർക്കുക. ഓരോരുത്തരെയും അവരുടെ അംഗത്വ രേഖയുമായി ബന്ധിപ്പിച്ചാൽ അംഗ സൗകര്യങ്ങളും ലഭിക്കും."),
    ]),
    ("setup", "office", ("First-time setup", "ആദ്യ ക്രമീകരണം"), [
        ("Settings: club name and address in both languages, registration number, wards, membership types with admission and annual fees, numbering formats, library rules, UPI ID, about text, cover photo and social links for the website.",
         "ക്രമീകരണങ്ങൾ: രണ്ട് ഭാഷയിലും ക്ലബ്ബിന്റെ പേരും വിലാസവും, രജിസ്ട്രേഷൻ നമ്പർ, വാർഡുകൾ, പ്രവേശന-വാർഷിക ഫീസ് സഹിതം അംഗത്വ തരങ്ങൾ, നമ്പറിംഗ് ഫോർമാറ്റുകൾ, ലൈബ്രറി നിയമങ്ങൾ, UPI ഐഡി, വെബ്സൈറ്റിനുള്ള വിവരണം, കവർ ഫോട്ടോ, സോഷ്യൽ ലിങ്കുകൾ."),
        ("Bring in the existing register: Members → 'Import register (Excel)', download the template, fill one member per row (family on the second sheet), upload, check the preview and import. Existing membership numbers are kept.",
         "നിലവിലുള്ള രജിസ്റ്റർ കൊണ്ടുവരിക: അംഗങ്ങൾ → 'രജിസ്റ്റർ ഇമ്പോർട്ട് (Excel)', ടെംപ്ലേറ്റ് ഡൗൺലോഡ് ചെയ്ത് ഓരോ വരിയിലും ഒരു അംഗം (കുടുംബം രണ്ടാം ഷീറ്റിൽ) പൂരിപ്പിച്ച് അപ്‌ലോഡ് ചെയ്യുക, പ്രിവ്യൂ പരിശോധിച്ച് ഇമ്പോർട്ട് ചെയ്യുക. നിലവിലുള്ള അംഗത്വ നമ്പറുകൾ നിലനിൽക്കും."),
        ("Committees → add the executive committee members with designations; they appear as office bearers on the website and in the annual report.",
         "കമ്മിറ്റികൾ → എക്സിക്യൂട്ടീവ് കമ്മിറ്റി അംഗങ്ങളെ സ്ഥാനങ്ങൾ സഹിതം ചേർക്കുക; അവർ വെബ്സൈറ്റിലും വാർഷിക റിപ്പോർട്ടിലും ഭാരവാഹികളായി കാണിക്കും."),
    ]),
    ("applications", "office", ("Applications and members", "അപേക്ഷകളും അംഗങ്ങളും"), [
        ("'Applications' lists new self-registrations with family details and a WhatsApp button. Approve to issue the membership number (automatic, or type an existing one), or reject with a note; the applicant is messaged either way. Admission fee and the year's subscription become due.",
         "'അപേക്ഷകൾ'-ൽ പുതിയ സ്വയം രജിസ്ട്രേഷനുകൾ കുടുംബവിവരങ്ങളും വാട്സ്ആപ്പ് ബട്ടണും സഹിതം കാണാം. അംഗീകരിച്ചാൽ അംഗത്വ നമ്പർ നൽകും (ഓട്ടോമാറ്റിക്, അല്ലെങ്കിൽ നിലവിലുള്ളത് ടൈപ്പ് ചെയ്യാം); കുറിപ്പോടെ നിരസിക്കാം; രണ്ടായാലും അപേക്ഷകന് സന്ദേശം പോകും. പ്രവേശന ഫീസും ആ വർഷത്തെ വരിസംഖ്യയും അടയ്ക്കാനുള്ളതായി രേഖപ്പെടുത്തും."),
        ("'Members' is the register: search, filter by ward, type or blood group, open a member for details, family, payments, books and timeline. 'Office entry' adds a member directly. 'Print cards' prints membership cards on A4; the e-card is on each member's profile.",
         "'അംഗങ്ങൾ' ആണ് രജിസ്റ്റർ: തിരയുക, വാർഡ്, തരം, രക്തഗ്രൂപ്പ് കൊണ്ട് ഫിൽട്ടർ ചെയ്യുക, വിവരങ്ങൾ, കുടുംബം, പണമിടപാടുകൾ, പുസ്തകങ്ങൾ, ചരിത്രം കാണാൻ അംഗത്തെ തുറക്കുക. 'ഓഫീസ് എൻട്രി' നേരിട്ട് അംഗത്തെ ചേർക്കുന്നു. 'കാർഡുകൾ പ്രിന്റ്' A4-ൽ അംഗത്വ കാർഡുകൾ പ്രിന്റ് ചെയ്യുന്നു; ഇ-കാർഡ് ഓരോ അംഗത്തിന്റെയും പ്രൊഫൈലിലുണ്ട്."),
        ("Change a member's status (inactive, suspended, resigned, deceased) from their page; it also switches off their sign-in.",
         "അംഗത്തിന്റെ പേജിൽ നിന്ന് നില മാറ്റാം (നിഷ്ക്രിയം, സസ്പെൻഡ്, രാജി, അന്തരിച്ചു); അതോടെ അവരുടെ പ്രവേശനവും നിലയ്ക്കും."),
    ]),
    ("publish", "office", ("Publishing and broadcasts", "പ്രസിദ്ധീകരണവും സന്ദേശങ്ങളും"), [
        ("News & events → 'New': choose the type (news, notice, event, camp, competition, social activity), write in both languages, set date, venue and audience. For competitions add items by age group. Publish and tick the channels; every member gets it in their own language.",
         "വാർത്തകളും പരിപാടികളും → 'പുതിയത്': തരം തിരഞ്ഞെടുക്കുക (വാർത്ത, അറിയിപ്പ്, പരിപാടി, ക്യാമ്പ്, മത്സരം, സാമൂഹിക പ്രവർത്തനം), രണ്ട് ഭാഷയിലും എഴുതുക, തീയതി, സ്ഥലം, ആർക്കെല്ലാം എന്നിവ നൽകുക. മത്സരങ്ങൾക്ക് പ്രായ വിഭാഗം തിരിച്ച് ഇനങ്ങൾ ചേർക്കുക. പ്രസിദ്ധീകരിച്ച് ചാനലുകൾ ടിക്ക് ചെയ്യുക; ഓരോ അംഗത്തിനും സ്വന്തം ഭാഷയിൽ ലഭിക്കും."),
        ("Public posts get a shareable page for WhatsApp groups. After the event, enter results (or let judges score and fill results from the ranking), add photos, and mark attendance by scanning cards.",
         "പൊതു പോസ്റ്റുകൾക്ക് വാട്സ്ആപ്പ് ഗ്രൂപ്പുകൾക്കായി പങ്കുവയ്ക്കാവുന്ന പേജ് ലഭിക്കും. പരിപാടിക്ക് ശേഷം ഫലങ്ങൾ രേഖപ്പെടുത്തുക (അല്ലെങ്കിൽ വിധികർത്താക്കൾ സ്കോർ ചെയ്ത് റാങ്കിംഗിൽ നിന്ന് ഫലം നിറയ്ക്കട്ടെ), ഫോട്ടോകൾ ചേർക്കുക, കാർഡ് സ്കാൻ ചെയ്ത് ഹാജർ രേഖപ്പെടുത്തുക."),
        ("'Broadcast' sends a message to all members, a ward, a type, a committee, an event's registrants, a blood group or hand-picked members, now or at a scheduled time. The 'Blood donor request' button fills an urgent appeal for one blood group. 'Outbox' shows every message and its delivery; channels that are not configured yet show as 'demo'.",
         "'സന്ദേശം അയയ്ക്കുക' എല്ലാ അംഗങ്ങൾക്കോ ഒരു വാർഡ്, തരം, കമ്മിറ്റി, പരിപാടിയുടെ രജിസ്ട്രേഷനുകൾ, രക്തഗ്രൂപ്പ്, തിരഞ്ഞെടുത്ത അംഗങ്ങൾ എന്നിവർക്കോ ഇപ്പോഴോ നിശ്ചിത സമയത്തോ സന്ദേശം അയയ്ക്കുന്നു. 'രക്തദാതാവിനുള്ള അഭ്യർത്ഥന' ബട്ടൺ ഒരു രക്തഗ്രൂപ്പിനുള്ള അടിയന്തര അഭ്യർത്ഥന തയ്യാറാക്കും. 'അയച്ച സന്ദേശങ്ങൾ'-ൽ ഓരോ സന്ദേശവും അതിന്റെ നിലയും കാണാം; ക്രമീകരിക്കാത്ത ചാനലുകൾ 'ഡെമോ' ആയി കാണിക്കും."),
    ]),
    ("meetings", "office", ("Committees, meetings and minutes", "കമ്മിറ്റികൾ, യോഗങ്ങൾ, മിനിറ്റ്സ്"), [
        ("Create a meeting under the committee with date, venue and agenda items, then 'Send notice'; members get the agenda. On the day, mark attendance (or scan cards); the quorum shows at once.",
         "കമ്മിറ്റിക്ക് കീഴിൽ തീയതി, സ്ഥലം, അജണ്ട ഇനങ്ങൾ സഹിതം യോഗം സൃഷ്ടിച്ച് 'അറിയിപ്പ് അയയ്ക്കുക'; അംഗങ്ങൾക്ക് അജണ്ട ലഭിക്കും. അന്നേദിവസം ഹാജർ രേഖപ്പെടുത്തുക (അല്ലെങ്കിൽ കാർഡ് സ്കാൻ ചെയ്യുക); ക്വോറം ഉടൻ കാണാം."),
        ("Record each item's decision (with proposer, seconder, votes and resolution number), add action items with an owner and due date (the owner is notified), then 'Publish minutes' so the committee can read them. The secretary or president signs off, after which the minutes are frozen. 'Print' gives a bilingual copy for the minutes book.",
         "ഓരോ ഇനത്തിന്റെയും തീരുമാനം (അവതരിപ്പിച്ചയാൾ, പിന്താങ്ങിയയാൾ, വോട്ടുകൾ, പ്രമേയ നമ്പർ സഹിതം) രേഖപ്പെടുത്തുക, ചുമതലക്കാരനും അവസാന തീയതിയും സഹിതം ചുമതലകൾ ചേർക്കുക (ചുമതലക്കാരന് അറിയിപ്പ് പോകും), പിന്നെ 'മിനിറ്റ്സ് പ്രസിദ്ധീകരിക്കുക' - കമ്മിറ്റിക്ക് വായിക്കാം. സെക്രട്ടറിയോ പ്രസിഡന്റോ അംഗീകരിച്ചാൽ മിനിറ്റ്സ് മരവിപ്പിക്കും. 'പ്രിന്റ്' മിനിറ്റ്സ് പുസ്തകത്തിനുള്ള ദ്വിഭാഷാ പകർപ്പ് നൽകും."),
        ("'Action items' tracks every task across meetings; 'Plans' holds the annual plan with budget and progress.",
         "'ചുമതലകൾ' എല്ലാ യോഗങ്ങളിലെയും ജോലികൾ പിന്തുടരുന്നു; 'പദ്ധതികൾ'-ൽ ബജറ്റും പുരോഗതിയും സഹിതം വാർഷിക പദ്ധതി."),
    ]),
    ("library_o", "office", ("Library desk", "ലൈബ്രറി ഡെസ്ക്"), [
        ("Add a book with its copies; accession numbers are issued automatically or typed. 'Issue / return': pick the member, type or scan the accession number. Fines are calculated on return and recorded as a receipt. Reservations are queued and the next member is messaged when a copy returns.",
         "പുസ്തകം പ്രതികൾ സഹിതം ചേർക്കുക; അക്സഷൻ നമ്പറുകൾ ഓട്ടോമാറ്റിക് ആയോ ടൈപ്പ് ചെയ്തോ നൽകാം. 'നൽകൽ / തിരികെ': അംഗത്തെ തിരഞ്ഞെടുത്ത് അക്സഷൻ നമ്പർ ടൈപ്പ് ചെയ്യുകയോ സ്കാൻ ചെയ്യുകയോ ചെയ്യുക. തിരികെ നൽകുമ്പോൾ പിഴ കണക്കാക്കി രസീതായി രേഖപ്പെടുത്തും. റിസർവേഷനുകൾ ക്യൂവിലാകും; പ്രതി തിരികെ വന്നാൽ അടുത്ത അംഗത്തിന് സന്ദേശം പോകും."),
        ("'Reading room' is the daily visitor register (scan cards for speed); 'Newspapers & periodicals' tracks subscriptions and daily receipt. 'Assets' is the register of chairs, equipment and the like with a lending record.",
         "'വായനശാല' ദൈനംദിന സന്ദർശക രജിസ്റ്ററാണ് (വേഗത്തിന് കാർഡ് സ്കാൻ ചെയ്യുക); 'പത്രങ്ങളും ആനുകാലികങ്ങളും' വരിസംഖ്യയും ദിവസേനയുള്ള ലഭ്യതയും പിന്തുടരുന്നു. 'ആസ്തികൾ' കസേരകൾ, ഉപകരണങ്ങൾ തുടങ്ങിയവയുടെ രജിസ്റ്ററാണ്, കടം നൽകിയതിന്റെ രേഖയും."),
    ]),
    ("accounts", "office", ("Accounts, dues and bookings", "കണക്കുകൾ, കുടിശ്ശിക, ബുക്കിംഗ്"), [
        ("'Accounts': receipts and payment vouchers by head, numbered per year; a receipt against a member settles their dues and is messaged to them. 'Dues': generate the year's subscriptions once, see defaulters, send reminders, record a receipt from the row.",
         "'കണക്കുകൾ': ഇനം തിരിച്ച് രസീതുകളും ചെലവ് വൗച്ചറുകളും, വർഷം തോറും നമ്പർ; അംഗത്തിനെതിരെയുള്ള രസീത് കുടിശ്ശിക തീർക്കും, അംഗത്തിന് സന്ദേശവും പോകും. 'കുടിശ്ശിക': വർഷത്തെ വരിസംഖ്യ ഒരിക്കൽ സൃഷ്ടിക്കുക, കുടിശ്ശികക്കാരെ കാണുക, ഓർമ്മപ്പെടുത്തൽ അയയ്ക്കുക, വരിയിൽ നിന്ന് തന്നെ രസീത് രേഖപ്പെടുത്തുക."),
        ("'UPI payments to confirm': members who paid by UPI appear here with the transaction number; check the bank statement and confirm (receipt issued) or reject with a reason. 'Online payments' lists gateway orders.",
         "'സ്ഥിരീകരിക്കേണ്ട UPI പേയ്മെന്റുകൾ': UPI വഴി അടച്ച അംഗങ്ങൾ ഇടപാട് നമ്പറോടെ ഇവിടെ വരും; ബാങ്ക് സ്റ്റേറ്റ്മെന്റ് പരിശോധിച്ച് സ്ഥിരീകരിക്കുക (രസീത് നൽകും) അല്ലെങ്കിൽ കാരണം സഹിതം നിരസിക്കുക. 'ഓൺലൈൻ പേയ്മെന്റുകൾ' ഗേറ്റ്‌വേ ഓർഡറുകൾ കാണിക്കും."),
        ("'Hall & ground booking': add facilities with rates; members request slots, the office confirms and records the payment in one step; the calendar prevents clashes.",
         "'ഹാൾ & ഗ്രൗണ്ട് ബുക്കിംഗ്': നിരക്കുകൾ സഹിതം സൗകര്യങ്ങൾ ചേർക്കുക; അംഗങ്ങൾ സമയം അഭ്യർത്ഥിക്കും, ഓഫീസ് ഒരൊറ്റ ഘട്ടത്തിൽ സ്ഥിരീകരിച്ച് പണം രേഖപ്പെടുത്തും; കലണ്ടർ സമയം കൂടിക്കലരുന്നത് തടയും."),
    ]),
    ("reports", "office", ("Reports, website, backups", "റിപ്പോർട്ടുകൾ, വെബ്സൈറ്റ്, ബാക്കപ്പുകൾ"), [
        ("'Reports' gives membership, participation, attendance and library statistics; 'Annual report' assembles the year for the AGM, printable in either language. 'Polls & elections' runs votes and office elections.",
         "'റിപ്പോർട്ടുകൾ' അംഗത്വം, പങ്കാളിത്തം, ഹാജർ, ലൈബ്രറി സ്ഥിതിവിവരങ്ങൾ നൽകുന്നു; 'വാർഷിക റിപ്പോർട്ട്' പൊതുയോഗത്തിനായി വർഷം മുഴുവൻ ഒരുക്കുന്നു, ഏത് ഭാഷയിലും പ്രിന്റ് ചെയ്യാം. 'വോട്ടെടുപ്പും തിരഞ്ഞെടുപ്പും' വോട്ടെടുപ്പുകളും ഭാരവാഹി തിരഞ്ഞെടുപ്പും നടത്തുന്നു."),
        ("The public website (the 'Website' link) shows the about text, office bearers, public events and news, documents, photos and contact; it updates itself from what you publish.",
         "പൊതു വെബ്സൈറ്റ് ('വെബ്സൈറ്റ്' ലിങ്ക്) വിവരണം, ഭാരവാഹികൾ, പൊതു പരിപാടികളും വാർത്തകളും, രേഖകൾ, ഫോട്ടോകൾ, ബന്ധപ്പെടാനുള്ള വിവരങ്ങൾ കാണിക്കുന്നു; താങ്കൾ പ്രസിദ്ധീകരിക്കുന്നതിൽ നിന്ന് അത് സ്വയം പുതുക്കും."),
        ("A backup of the database and uploads is taken every night; with Google Drive configured it is also stored off-site. Settings → Backups shows the last result and a 'Back up now' button. WhatsApp, SMS, e-mail, online payments and Drive are switched on by the administrator in the server's .env file as described in the README.",
         "ഡാറ്റാബേസിന്റെയും അപ്‌ലോഡുകളുടെയും ബാക്കപ്പ് എല്ലാ രാത്രിയും എടുക്കും; ഗൂഗിൾ ഡ്രൈവ് ക്രമീകരിച്ചാൽ പുറത്തും സൂക്ഷിക്കും. ക്രമീകരണങ്ങൾ → ബാക്കപ്പുകൾ-ൽ അവസാന ഫലവും 'ഇപ്പോൾ ബാക്കപ്പ്' ബട്ടണും. വാട്സ്ആപ്പ്, SMS, ഇ-മെയിൽ, ഓൺലൈൻ പേയ്മെന്റ്, ഡ്രൈവ് എന്നിവ README-ൽ പറഞ്ഞപോലെ സെർവറിന്റെ .env ഫയലിൽ അഡ്മിനിസ്ട്രേറ്റർ ഓൺ ചെയ്യുന്നു."),
    ]),
]


def sections(lang):
    i = 1 if lang == "ml" else 0
    return [{"key": k, "audience": a, "title": t[i], "paragraphs": [p[i] for p in ps]} for k, a, t, ps in SECTIONS]


@router.get("/api/help")
def help_json(lang: str = ""):
    lang = lang if lang in ("en", "ml") else db.setting("default_lang")
    return {"lang": lang, "sections": sections(lang)}


@router.get("/help", response_class=HTMLResponse)
def help_page(lang: str = ""):
    lang = lang if lang in ("en", "ml") else db.setting("default_lang")
    other = "en" if lang == "ml" else "ml"
    s = db.settings_all(); e = html.escape
    L = {"en": ("Handbook", "For members", "For office bearers", "Contents"), "ml": ("കൈപ്പുസ്തകം", "അംഗങ്ങൾക്ക്", "ഭാരവാഹികൾക്ക്", "ഉള്ളടക്കം")}[lang]
    secs = sections(lang)
    toc = "".join(f"<li><a href='#{x['key']}'>{e(x['title'])}</a></li>" for x in secs)
    body = ""
    for aud, head in (("member", L[1]), ("office", L[2])):
        body += f"<h2 class=part>{head}</h2>"
        for x in secs:
            if x["audience"] != aud:
                continue
            body += f"<section id='{x['key']}'><h3>{e(x['title'])}</h3>{''.join('<p>' + e(p) + '</p>' for p in x['paragraphs'])}</section>"
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{L[0]} · {e(s['club_short'])}</title>
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;max-width:820px;margin:0 auto;padding:24px 18px 60px;color:#1D2A28;line-height:1.6;background:#F7F4EC}}html[lang=ml] body{{font-family:Manjari,Inter,sans-serif;font-size:1.05rem}}
h1{{color:#0F4C45;margin:.2em 0}}h2.part{{color:#fff;background:#0F4C45;padding:8px 14px;border-radius:10px;margin-top:30px;font-size:1.15rem}}h3{{color:#0F4C45;margin:22px 0 6px;border-bottom:2px solid #E3DED2;padding-bottom:4px}}
p{{margin:8px 0}}a{{color:#196B61}}.top{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}.btn{{background:#0F4C45;color:#fff;padding:7px 12px;border-radius:9px;text-decoration:none;font-weight:600}}
.toc{{background:#fff;border:1px solid #E3DED2;border-radius:12px;padding:12px 18px 12px 34px;columns:2;font-size:.95rem}}.m{{color:#5B6B68;font-size:.85rem}}@media print{{.btn{{display:none}}body{{background:#fff}}}}</style></head>
<body><div class="top"><div style="flex:1"><div class=m>{e(s['club_name_ml' if lang == 'ml' else 'club_name_en'])}</div><h1>{L[0]}</h1></div><a class="btn" href="/help?lang={other}">{'English' if lang == 'ml' else 'മലയാളം'}</a><a class="btn" href="#" onclick="window.print();return false">🖨</a></div>
<h2 style="font-size:1rem;color:#5B6B68">{L[3]}</h2><ol class="toc">{toc}</ol>{body}<p class=m style="margin-top:40px">{e(s['footer_credit'])}</p></body></html>"""

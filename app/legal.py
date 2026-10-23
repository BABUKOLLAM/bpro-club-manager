"""Terms of service and privacy policy for the platform, at /terms and /privacy, in English and Malayalam.

The texts are a reasonable starting point for a small Indian SaaS run by an operator (product and operator names come
from the platform settings). They describe how the product actually behaves: the club is the data fiduciary for its
members' data, the operator processes it on the club's behalf (Digital Personal Data Protection Act, 2023), nothing is
deleted on non-payment, and so on. The operator should have them reviewed before going live.
"""
import datetime as dt
import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
EFFECTIVE = "2026-10-23"

# Each section: (heading_en, heading_ml, [paragraph_en, ...], [paragraph_ml, ...]). {product}, {operator}, {support} are filled in.
TERMS = [
    ("1. The service", "1. സേവനം",
     ["{product} is an online service for managing a club, library or reading room: membership, communication, events, committees, library, accounts and related functions. It is provided by {operator} (\"we\", \"the operator\").",
      "A club (\"the club\", \"you\") opens an account by signing up on the website or by being added by the operator. The person who signs up confirms that they are authorised by the club to do so."],
     ["{product} ഒരു ക്ലബ്ബ്, ലൈബ്രറി അല്ലെങ്കിൽ വായനശാലയുടെ നടത്തിപ്പിനുള്ള ഓൺലൈൻ സേവനമാണ്: അംഗത്വം, ആശയവിനിമയം, പരിപാടികൾ, കമ്മിറ്റികൾ, ലൈബ്രറി, കണക്കുകൾ, അനുബന്ധ പ്രവർത്തനങ്ങൾ. ഇത് നൽകുന്നത് {operator} (\"ഞങ്ങൾ\", \"ഓപ്പറേറ്റർ\") ആണ്.",
      "ഒരു ക്ലബ്ബ് (\"ക്ലബ്ബ്\", \"നിങ്ങൾ\") വെബ്സൈറ്റിൽ സൈൻ അപ്പ് ചെയ്തോ ഓപ്പറേറ്റർ ചേർത്തോ അക്കൗണ്ട് തുറക്കുന്നു. സൈൻ അപ്പ് ചെയ്യുന്ന വ്യക്തി അതിന് ക്ലബ്ബിന്റെ അധികാരമുണ്ടെന്ന് ഉറപ്പുനൽകുന്നു."]),
    ("2. Trial, price and payment", "2. ട്രയൽ, വില, പണമടയ്ക്കൽ",
     ["A new club gets a free trial of the length shown on the pricing page. No payment details are needed for the trial.",
      "After the trial the club pays a yearly subscription. The price is the one shown on the pricing page on the day of payment: a flat amount for small clubs, otherwise an amount per active member, counted on the club's own register at that moment. Prices are in Indian rupees and include applicable taxes unless stated otherwise.",
      "Payment is made online through the operator's payment gateway or by UPI / bank transfer with a reference the operator confirms. A paid year starts when the payment is confirmed, or when the previous paid year ends, whichever is later.",
      "Prices may change for the next renewal; the club is told at least 30 days before the renewal date. A paid year is never re-priced."],
     ["പുതിയ ക്ലബ്ബിന് വില പേജിൽ കാണിച്ചിരിക്കുന്ന ദൈർഘ്യത്തിൽ സൗജന്യ ട്രയൽ ലഭിക്കും. ട്രയലിന് പേയ്മെന്റ് വിവരങ്ങൾ വേണ്ട.",
      "ട്രയലിനു ശേഷം ക്ലബ്ബ് വാർഷിക സബ്സ്ക്രിപ്ഷൻ അടയ്ക്കുന്നു. പണമടയ്ക്കുന്ന ദിവസം വില പേജിൽ കാണിച്ചിരിക്കുന്ന വിലയാണ് ബാധകം: ചെറിയ ക്ലബ്ബുകൾക്ക് മൊത്തം തുക; അല്ലെങ്കിൽ ആ നിമിഷം ക്ലബ്ബിന്റെ രജിസ്റ്ററിലുള്ള സജീവ അംഗങ്ങളുടെ എണ്ണത്തിന് അനുസരിച്ചുള്ള തുക. വിലകൾ ഇന്ത്യൻ രൂപയിൽ; മറിച്ച് പറയാത്ത പക്ഷം ബാധകമായ നികുതികൾ ഉൾപ്പെടെ.",
      "ഓപ്പറേറ്ററുടെ പേയ്മെന്റ് ഗേറ്റ്‌വേ വഴി ഓൺലൈനായോ, ഓപ്പറേറ്റർ സ്ഥിരീകരിക്കുന്ന റഫറൻസോടെ UPI / ബാങ്ക് ട്രാൻസ്ഫർ വഴിയോ പണമടയ്ക്കാം. പേയ്മെന്റ് സ്ഥിരീകരിക്കുമ്പോഴോ മുൻ വർഷം അവസാനിക്കുമ്പോഴോ, ഏതാണോ വൈകിയത്, അടച്ച വർഷം തുടങ്ങുന്നു.",
      "അടുത്ത പുതുക്കലിന് വില മാറാം; പുതുക്കൽ തീയതിക്ക് കുറഞ്ഞത് 30 ദിവസം മുമ്പ് ക്ലബ്ബിനെ അറിയിക്കും. അടച്ച വർഷത്തിന്റെ വില ഒരിക്കലും മാറ്റില്ല."]),
    ("3. If a subscription is not paid", "3. സബ്സ്ക്രിപ്ഷൻ അടയ്ക്കാതിരുന്നാൽ",
     ["When the trial or the paid year ends, the club has a grace period (shown on the pricing page) during which everything keeps working and office bearers are reminded.",
      "After the grace period the club becomes read-only: members and office bearers can still sign in, read and export everything, and the club can pay; other changes are refused. Nothing is deleted. Paying reopens the club at once.",
      "A club that stays unpaid for 12 months may be deleted after a final notice to the contact on record, with 30 days to pay or to ask for an export."],
     ["ട്രയലോ അടച്ച വർഷമോ അവസാനിക്കുമ്പോൾ ക്ലബ്ബിന് ഒരു ഇളവ് കാലയളവ് (വില പേജിൽ കാണിച്ചിരിക്കുന്നു) ലഭിക്കും; അതിൽ എല്ലാം പ്രവർത്തിക്കും, ഭാരവാഹികളെ ഓർമ്മപ്പെടുത്തും.",
      "ഇളവ് കാലയളവിന് ശേഷം ക്ലബ്ബ് വായിക്കാൻ മാത്രമാകും: അംഗങ്ങൾക്കും ഭാരവാഹികൾക്കും പ്രവേശിക്കാനും എല്ലാം വായിക്കാനും എക്സ്പോർട്ട് ചെയ്യാനും കഴിയും, ക്ലബ്ബിന് പണമടയ്ക്കാം; മറ്റ് മാറ്റങ്ങൾ നിരസിക്കും. ഒന്നും നഷ്ടപ്പെടില്ല. പണമടച്ചാൽ ഉടൻ ക്ലബ്ബ് വീണ്ടും തുറക്കും.",
      "12 മാസം അടയ്ക്കാതെ തുടരുന്ന ക്ലബ്ബ്, രേഖയിലുള്ള ബന്ധപ്പെടാനുള്ള ആളിന് അവസാന അറിയിപ്പ് നൽകി, പണമടയ്ക്കാനോ എക്സ്പോർട്ട് ആവശ്യപ്പെടാനോ 30 ദിവസം നൽകിയ ശേഷം നീക്കം ചെയ്തേക്കാം."]),
    ("4. The club's data", "4. ക്ലബ്ബിന്റെ ഡാറ്റ",
     ["Everything the club enters belongs to the club: the members' register, family details, photos, minutes, accounts, documents and messages. The operator processes this data only to provide the service, as described in the privacy policy, and does not sell it or use it for advertising.",
      "The club is responsible for the data it enters: for collecting it lawfully from its members, for keeping it accurate, and for choosing who among its office bearers may see and change it.",
      "The club can export its data at any time (CSV and Excel from the app; a full copy on request) and can ask the operator to delete the club and all its data."],
     ["ക്ലബ്ബ് നൽകുന്നതെല്ലാം ക്ലബ്ബിന്റേതാണ്: അംഗങ്ങളുടെ രജിസ്റ്റർ, കുടുംബ വിവരങ്ങൾ, ഫോട്ടോകൾ, മിനിറ്റ്സ്, കണക്കുകൾ, രേഖകൾ, സന്ദേശങ്ങൾ. സ്വകാര്യതാ നയത്തിൽ പറയുന്നതുപോലെ സേവനം നൽകാൻ മാത്രമേ ഓപ്പറേറ്റർ ഈ ഡാറ്റ ഉപയോഗിക്കൂ; വിൽക്കുകയോ പരസ്യത്തിന് ഉപയോഗിക്കുകയോ ഇല്ല.",
      "നൽകുന്ന ഡാറ്റയ്ക്ക് ക്ലബ്ബാണ് ഉത്തരവാദി: അംഗങ്ങളിൽ നിന്ന് നിയമാനുസൃതമായി ശേഖരിക്കുന്നതിനും കൃത്യമായി സൂക്ഷിക്കുന്നതിനും ഏതൊക്കെ ഭാരവാഹികൾക്ക് കാണാനും മാറ്റാനും കഴിയുമെന്ന് തീരുമാനിക്കുന്നതിനും.",
      "ക്ലബ്ബിന് എപ്പോൾ വേണമെങ്കിലും ഡാറ്റ എക്സ്പോർട്ട് ചെയ്യാം (ആപ്പിൽ നിന്ന് CSV, Excel; ആവശ്യപ്പെട്ടാൽ മുഴുവൻ പകർപ്പ്); ക്ലബ്ബും അതിന്റെ എല്ലാ ഡാറ്റയും നീക്കം ചെയ്യാൻ ഓപ്പറേറ്ററോട് ആവശ്യപ്പെടാം."]),
    ("5. Acceptable use", "5. അനുവദനീയമായ ഉപയോഗം",
     ["The service is for the club's own members and activities. The club must not use it to send unsolicited messages to people who are not its members or applicants, to upload unlawful content, or to attempt to access another club's data.",
      "Messages sent through WhatsApp, SMS and e-mail are subject to the rules of those providers (for example DLT registration for SMS in India and Meta's WhatsApp policies). Charges those providers make are the club's own when the club uses its own accounts."],
     ["സേവനം ക്ലബ്ബിന്റെ സ്വന്തം അംഗങ്ങൾക്കും പ്രവർത്തനങ്ങൾക്കും വേണ്ടിയാണ്. അംഗങ്ങളോ അപേക്ഷകരോ അല്ലാത്തവർക്ക് ആവശ്യപ്പെടാത്ത സന്ദേശങ്ങൾ അയയ്ക്കാനോ, നിയമവിരുദ്ധ ഉള്ളടക്കം അപ്‌ലോഡ് ചെയ്യാനോ, മറ്റൊരു ക്ലബ്ബിന്റെ ഡാറ്റയിൽ കടക്കാൻ ശ്രമിക്കാനോ ഇത് ഉപയോഗിക്കരുത്.",
      "വാട്സ്ആപ്പ്, SMS, ഇ-മെയിൽ വഴിയുള്ള സന്ദേശങ്ങൾക്ക് അതത് ദാതാക്കളുടെ നിയമങ്ങൾ ബാധകമാണ് (ഉദാ: ഇന്ത്യയിൽ SMS-ന് DLT രജിസ്ട്രേഷൻ, Meta-യുടെ വാട്സ്ആപ്പ് നയങ്ങൾ). ക്ലബ്ബ് സ്വന്തം അക്കൗണ്ടുകൾ ഉപയോഗിക്കുമ്പോൾ ആ ദാതാക്കളുടെ നിരക്കുകൾ ക്ലബ്ബിന്റേതാണ്."]),
    ("6. Availability and support", "6. ലഭ്യതയും സഹായവും",
     ["We aim to keep the service available at all times and to take a backup of every club every night, but we do not guarantee uninterrupted availability. Planned maintenance is announced in advance where possible.",
      "Support is provided through the contact shown in the app ({support}). We answer within two working days."],
     ["സേവനം എപ്പോഴും ലഭ്യമാക്കാനും എല്ലാ രാത്രിയും ഓരോ ക്ലബ്ബിന്റെയും ബാക്കപ്പ് എടുക്കാനും ഞങ്ങൾ ശ്രമിക്കുന്നു; എന്നാൽ തടസ്സമില്ലാത്ത ലഭ്യത ഉറപ്പുനൽകുന്നില്ല. ആസൂത്രിത അറ്റകുറ്റപ്പണി കഴിയുന്നിടത്തോളം മുൻകൂട്ടി അറിയിക്കും.",
      "ആപ്പിൽ കാണിച്ചിരിക്കുന്ന ബന്ധപ്പെടാനുള്ള വഴിയിലൂടെ ({support}) സഹായം ലഭിക്കും. രണ്ട് പ്രവൃത്തി ദിവസങ്ങൾക്കുള്ളിൽ മറുപടി നൽകും."]),
    ("7. Liability", "7. ബാധ്യത",
     ["The service is provided as is. To the extent the law allows, the operator's liability for any claim connected with the service is limited to the subscription paid by the club for the year in which the claim arose. The operator is not liable for loss caused by the club's own entries, by third-party providers (messaging, payment gateways, hosting) or by events beyond its control."],
     ["സേവനം ഉള്ളതുപോലെ നൽകുന്നു. നിയമം അനുവദിക്കുന്ന പരിധിയിൽ, സേവനവുമായി ബന്ധപ്പെട്ട ഏതൊരു ക്ലെയിമിനും ഓപ്പറേറ്ററുടെ ബാധ്യത ക്ലെയിം ഉണ്ടായ വർഷം ക്ലബ്ബ് അടച്ച സബ്സ്ക്രിപ്ഷൻ തുകയിൽ ഒതുങ്ങും. ക്ലബ്ബിന്റെ സ്വന്തം എൻട്രികൾ, മൂന്നാം കക്ഷി ദാതാക്കൾ (സന്ദേശം, പേയ്മെന്റ് ഗേറ്റ്‌വേ, ഹോസ്റ്റിംഗ്), നിയന്ത്രണത്തിന് പുറത്തുള്ള സംഭവങ്ങൾ എന്നിവയാൽ ഉണ്ടാകുന്ന നഷ്ടത്തിന് ഓപ്പറേറ്റർ ബാധ്യസ്ഥനല്ല."]),
    ("8. Ending the service", "8. സേവനം അവസാനിപ്പിക്കൽ",
     ["The club may stop at any time; the paid year is not refunded, except within 14 days of the first payment if the club has not used the service beyond the trial.",
      "The operator may suspend a club that breaks these terms, after a warning except in urgent cases, and may stop offering the service altogether with 90 days' notice, during which the club can export its data."],
     ["ക്ലബ്ബിന് എപ്പോൾ വേണമെങ്കിലും നിർത്താം; അടച്ച വർഷത്തിന്റെ തുക തിരികെ നൽകില്ല; ട്രയലിനപ്പുറം സേവനം ഉപയോഗിച്ചിട്ടില്ലെങ്കിൽ ആദ്യ പേയ്മെന്റിന്റെ 14 ദിവസത്തിനുള്ളിൽ തിരികെ നൽകും.",
      "ഈ വ്യവസ്ഥകൾ ലംഘിക്കുന്ന ക്ലബ്ബിനെ, അടിയന്തര സാഹചര്യങ്ങളിലൊഴികെ മുന്നറിയിപ്പിന് ശേഷം, ഓപ്പറേറ്റർക്ക് താൽക്കാലികമായി നിർത്താം; 90 ദിവസത്തെ അറിയിപ്പോടെ സേവനം പൂർണ്ണമായി നിർത്താനും കഴിയും; ആ കാലയളവിൽ ക്ലബ്ബിന് ഡാറ്റ എക്സ്പോർട്ട് ചെയ്യാം."]),
    ("9. Changes and law", "9. മാറ്റങ്ങളും നിയമവും",
     ["We may update these terms; material changes are notified to the club's contact 30 days in advance. Continued use after that is acceptance.",
      "These terms are governed by the laws of India. Disputes are subject to the courts at Kottayam, Kerala."],
     ["ഈ വ്യവസ്ഥകൾ ഞങ്ങൾ പുതുക്കിയേക്കാം; പ്രധാന മാറ്റങ്ങൾ 30 ദിവസം മുമ്പ് ക്ലബ്ബിന്റെ ബന്ധപ്പെടാനുള്ള ആളെ അറിയിക്കും. അതിനുശേഷമുള്ള ഉപയോഗം സമ്മതമായി കണക്കാക്കും.",
      "ഈ വ്യവസ്ഥകൾക്ക് ഇന്ത്യയുടെ നിയമങ്ങൾ ബാധകമാണ്. തർക്കങ്ങൾ കേരളത്തിലെ കോട്ടയം കോടതികളുടെ അധികാരപരിധിയിലായിരിക്കും."]),
]

PRIVACY = [
    ("1. Who is responsible for your data", "1. നിങ്ങളുടെ ഡാറ്റയുടെ ഉത്തരവാദി ആര്",
     ["{product} is used by clubs to manage their members. When you apply to or are a member of a club, the <b>club</b> decides what it collects and why; in the words of India's Digital Personal Data Protection Act, 2023, the club is the data fiduciary. {operator} runs the software and the servers for the club and processes your data only on the club's instructions and as described here.",
      "Questions about your data in a particular club go to that club's office bearers (their contact is on the club's website and in the app). Questions about the platform go to {operator} ({support})."],
     ["ക്ലബ്ബുകൾ അംഗങ്ങളെ നിയന്ത്രിക്കാൻ {product} ഉപയോഗിക്കുന്നു. നിങ്ങൾ ഒരു ക്ലബ്ബിൽ അപേക്ഷിക്കുമ്പോഴോ അംഗമാകുമ്പോഴോ, എന്ത് ശേഖരിക്കണം, എന്തിന് എന്ന് തീരുമാനിക്കുന്നത് <b>ക്ലബ്ബ്</b> ആണ്; ഇന്ത്യയുടെ ഡിജിറ്റൽ വ്യക്തിഗത ഡാറ്റ സംരക്ഷണ നിയമം, 2023-ന്റെ ഭാഷയിൽ ക്ലബ്ബാണ് ഡാറ്റ ഫിഡ്യൂഷ്യറി. {operator} ക്ലബ്ബിനു വേണ്ടി സോഫ്റ്റ്‌വെയറും സെർവറുകളും നടത്തുന്നു; ക്ലബ്ബിന്റെ നിർദ്ദേശപ്രകാരവും ഇവിടെ പറയുന്നതുപോലെയും മാത്രം നിങ്ങളുടെ ഡാറ്റ പ്രോസസ്സ് ചെയ്യുന്നു.",
      "ഒരു ക്ലബ്ബിലെ നിങ്ങളുടെ ഡാറ്റയെക്കുറിച്ചുള്ള ചോദ്യങ്ങൾ ആ ക്ലബ്ബിന്റെ ഭാരവാഹികളോട് (അവരെ ബന്ധപ്പെടാനുള്ള വിവരം ക്ലബ്ബിന്റെ വെബ്സൈറ്റിലും ആപ്പിലും ഉണ്ട്). പ്ലാറ്റ്ഫോമിനെക്കുറിച്ചുള്ള ചോദ്യങ്ങൾ {operator}-നോട് ({support})."]),
    ("2. What is collected", "2. എന്തൊക്കെ ശേഖരിക്കുന്നു",
     ["<b>Members and applicants</b>: name (English and Malayalam), gender, date of birth, blood group, phone and WhatsApp number, e-mail, house name and address, ward, occupation, education, interests, ID proof number if the club asks for it, photo, membership type and number, dates joined and left.",
      "<b>Family members</b> entered by a member: name, relation, date of birth, blood group, phone.",
      "<b>Activity in the club</b>: event registrations and attendance, competition entries and scores, committee membership, meeting attendance, library loans, fines and reservations, reading-room visits, bookings, receipts and dues, votes cast (not the choice, in a secret ballot), messages sent to you and whether they were delivered.",
      "<b>Technical</b>: the sign-in session, the language you chose, notification preferences, the time of sign-ins and of changes you make (the audit log), and, if you turn on phone notifications, a push subscription token."],
     ["<b>അംഗങ്ങളും അപേക്ഷകരും</b>: പേര് (ഇംഗ്ലീഷും മലയാളവും), ലിംഗം, ജനനത്തീയതി, രക്തഗ്രൂപ്പ്, ഫോണും വാട്സ്ആപ്പ് നമ്പറും, ഇ-മെയിൽ, വീട്ടുപേരും വിലാസവും, വാർഡ്, തൊഴിൽ, വിദ്യാഭ്യാസം, താൽപ്പര്യങ്ങൾ, ക്ലബ്ബ് ചോദിച്ചാൽ ഐഡി പ്രൂഫ് നമ്പർ, ഫോട്ടോ, അംഗത്വ തരവും നമ്പറും, ചേർന്ന / വിട്ട തീയതികൾ.",
      "<b>കുടുംബാംഗങ്ങൾ</b> (അംഗം നൽകുന്നത്): പേര്, ബന്ധം, ജനനത്തീയതി, രക്തഗ്രൂപ്പ്, ഫോൺ.",
      "<b>ക്ലബ്ബിലെ പ്രവർത്തനം</b>: പരിപാടി രജിസ്ട്രേഷനും ഹാജരും, മത്സര എൻട്രികളും സ്കോറുകളും, കമ്മിറ്റി അംഗത്വം, യോഗ ഹാജർ, ലൈബ്രറി വായ്പകൾ, പിഴകൾ, റിസർവേഷനുകൾ, വായനശാല സന്ദർശനങ്ങൾ, ബുക്കിംഗുകൾ, രസീതുകളും കുടിശ്ശികയും, വോട്ട് ചെയ്തത് (രഹസ്യ ബാലറ്റിൽ തിരഞ്ഞെടുപ്പല്ല), നിങ്ങൾക്ക് അയച്ച സന്ദേശങ്ങളും അവ എത്തിയോ എന്നതും.",
      "<b>സാങ്കേതികം</b>: പ്രവേശന സെഷൻ, തിരഞ്ഞെടുത്ത ഭാഷ, അറിയിപ്പ് മുൻഗണനകൾ, പ്രവേശനങ്ങളുടെയും നിങ്ങൾ വരുത്തുന്ന മാറ്റങ്ങളുടെയും സമയം (ഓഡിറ്റ് ലോഗ്), ഫോൺ അറിയിപ്പുകൾ ഓണാക്കിയാൽ ഒരു പുഷ് സബ്സ്ക്രിപ്ഷൻ ടോക്കൺ."]),
    ("3. Why it is used", "3. എന്തിന് ഉപയോഗിക്കുന്നു",
     ["To run the club: the register and e-card, approvals, numbering, dues and receipts, library circulation, meetings and minutes, bookings, polls.",
      "To reach you: notices, event reminders, receipts, library reminders, birthday wishes and broadcasts from the club, on the channels you allow (WhatsApp, SMS, e-mail, app). You can switch channels off under Notification preferences; in-app notifications remain.",
      "Blood group: so the club can ask members and family members of a matching group to donate in an emergency.",
      "Directory: your phone number appears in the members directory only if you allow it under Notification preferences.",
      "Public website: only office bearers' names, designations, photos and, if they allow, phone numbers appear on the club's public website. Members' data is never public."],
     ["ക്ലബ്ബ് നടത്താൻ: രജിസ്റ്ററും ഇ-കാർഡും, അംഗീകാരങ്ങൾ, നമ്പറിംഗ്, കുടിശ്ശികയും രസീതുകളും, ലൈബ്രറി ഇഷ്യൂ, യോഗങ്ങളും മിനിറ്റ്സും, ബുക്കിംഗുകൾ, വോട്ടെടുപ്പുകൾ.",
      "നിങ്ങളെ ബന്ധപ്പെടാൻ: നോട്ടീസുകൾ, പരിപാടി ഓർമ്മപ്പെടുത്തലുകൾ, രസീതുകൾ, ലൈബ്രറി ഓർമ്മപ്പെടുത്തലുകൾ, ജന്മദിനാശംസകൾ, ക്ലബ്ബിന്റെ ബ്രോഡ്കാസ്റ്റുകൾ; നിങ്ങൾ അനുവദിക്കുന്ന ചാനലുകളിൽ (വാട്സ്ആപ്പ്, SMS, ഇ-മെയിൽ, ആപ്പ്). അറിയിപ്പ് മുൻഗണനകളിൽ ചാനലുകൾ ഓഫാക്കാം; ആപ്പ് അറിയിപ്പ് തുടരും.",
      "രക്തഗ്രൂപ്പ്: അടിയന്തര ഘട്ടത്തിൽ യോജിക്കുന്ന ഗ്രൂപ്പിലുള്ള അംഗങ്ങളോടും കുടുംബാംഗങ്ങളോടും രക്തദാനത്തിന് അഭ്യർത്ഥിക്കാൻ.",
      "ഡയറക്ടറി: അറിയിപ്പ് മുൻഗണനകളിൽ അനുവദിച്ചാൽ മാത്രമേ നിങ്ങളുടെ ഫോൺ നമ്പർ അംഗങ്ങളുടെ ഡയറക്ടറിയിൽ കാണൂ.",
      "പൊതു വെബ്സൈറ്റ്: ഭാരവാഹികളുടെ പേര്, പദവി, ഫോട്ടോ, അനുവദിച്ചാൽ ഫോൺ നമ്പർ മാത്രമേ ക്ലബ്ബിന്റെ പൊതു വെബ്സൈറ്റിൽ വരൂ. അംഗങ്ങളുടെ ഡാറ്റ ഒരിക്കലും പൊതുവല്ല."]),
    ("4. Who can see it", "4. ആർക്കൊക്കെ കാണാം",
     ["Your club's office bearers, each according to their role (for example the librarian sees loans, the treasurer sees payments). Every change they make is logged.",
      "Other members see only what you allow (your phone in the directory) and what the club publishes to members (minutes of general body meetings, event participants' names where the club shows them).",
      "Service providers that carry messages and payments, each receiving only what the service needs: Meta (WhatsApp Cloud API) receives your WhatsApp number and the message text; the SMS gateway receives your mobile number and the text; the e-mail provider receives your e-mail address and the message; Razorpay receives the payment amount and your name, phone and e-mail when you pay online. Google Drive receives encrypted-in-transit backup copies if the club or operator has enabled off-site backups.",
      "The operator's staff access a club's data only to support it, at the club's request, or to fix a fault. Data is never sold and never used for advertising."],
     ["നിങ്ങളുടെ ക്ലബ്ബിന്റെ ഭാരവാഹികൾ, ഓരോരുത്തരുടെയും റോളിന് അനുസരിച്ച് (ഉദാ: ലൈബ്രേറിയൻ വായ്പകൾ കാണുന്നു, ട്രഷറർ പേയ്മെന്റുകൾ). അവർ വരുത്തുന്ന ഓരോ മാറ്റവും രേഖപ്പെടുത്തുന്നു.",
      "മറ്റ് അംഗങ്ങൾ നിങ്ങൾ അനുവദിക്കുന്നതും (ഡയറക്ടറിയിലെ ഫോൺ) ക്ലബ്ബ് അംഗങ്ങൾക്ക് പ്രസിദ്ധീകരിക്കുന്നതും (ജനറൽ ബോഡി മിനിറ്റ്സ്, ക്ലബ്ബ് കാണിക്കുന്നിടത്ത് പരിപാടി പങ്കാളികളുടെ പേരുകൾ) മാത്രം കാണുന്നു.",
      "സന്ദേശങ്ങളും പേയ്മെന്റുകളും കൈകാര്യം ചെയ്യുന്ന സേവന ദാതാക്കൾ, ഓരോരുത്തർക്കും സേവനത്തിന് വേണ്ടത് മാത്രം: Meta (WhatsApp Cloud API)-ക്ക് നിങ്ങളുടെ വാട്സ്ആപ്പ് നമ്പറും സന്ദേശവും; SMS ഗേറ്റ്‌വേയ്ക്ക് മൊബൈൽ നമ്പറും സന്ദേശവും; ഇ-മെയിൽ ദാതാവിന് ഇ-മെയിൽ വിലാസവും സന്ദേശവും; ഓൺലൈനായി പണമടയ്ക്കുമ്പോൾ Razorpay-ക്ക് തുകയും നിങ്ങളുടെ പേര്, ഫോൺ, ഇ-മെയിലും. ക്ലബ്ബോ ഓപ്പറേറ്ററോ ഓഫ്-സൈറ്റ് ബാക്കപ്പ് ഓണാക്കിയിട്ടുണ്ടെങ്കിൽ Google Drive-ൽ ബാക്കപ്പ് പകർപ്പുകൾ (കൈമാറുമ്പോൾ എൻക്രിപ്റ്റ് ചെയ്തത്).",
      "ഓപ്പറേറ്ററുടെ ജീവനക്കാർ ഒരു ക്ലബ്ബിന്റെ ഡാറ്റ കാണുന്നത് ക്ലബ്ബിന്റെ ആവശ്യപ്രകാരം സഹായിക്കാനോ തകരാർ പരിഹരിക്കാനോ മാത്രം. ഡാറ്റ ഒരിക്കലും വിൽക്കുകയോ പരസ്യത്തിന് ഉപയോഗിക്കുകയോ ഇല്ല."]),
    ("5. Where it is kept and for how long", "5. എവിടെ, എത്ര കാലം സൂക്ഷിക്കുന്നു",
     ["Each club's data is kept in its own database on the operator's server in India, with nightly backups. Backups are kept for the number of days the club sets (default 14) and, off-site, for the same period.",
      "A member's data is kept as long as they are on the club's register and for the period the club's rules or the law require afterwards (accounts, for example, are kept for 8 years). A club that leaves can take a full export and have everything deleted."],
     ["ഓരോ ക്ലബ്ബിന്റെയും ഡാറ്റ ഇന്ത്യയിലെ ഓപ്പറേറ്ററുടെ സെർവറിൽ സ്വന്തം ഡാറ്റാബേസിൽ, രാത്രി ബാക്കപ്പുകളോടെ സൂക്ഷിക്കുന്നു. ക്ലബ്ബ് നിശ്ചയിക്കുന്ന ദിവസങ്ങൾ (ഡിഫോൾട്ട് 14) ബാക്കപ്പുകൾ സൂക്ഷിക്കും; ഓഫ്-സൈറ്റിലും അതേ കാലയളവ്.",
      "അംഗം ക്ലബ്ബിന്റെ രജിസ്റ്ററിലുള്ള കാലത്തോളവും അതിനുശേഷം ക്ലബ്ബിന്റെ നിയമാവലിയോ നിയമമോ ആവശ്യപ്പെടുന്ന കാലയളവിലും (ഉദാ: കണക്കുകൾ 8 വർഷം) അംഗത്തിന്റെ ഡാറ്റ സൂക്ഷിക്കും. വിട്ടുപോകുന്ന ക്ലബ്ബിന് മുഴുവൻ എക്സ്പോർട്ട് എടുത്ത് എല്ലാം നീക്കം ചെയ്യിക്കാം."]),
    ("6. Your rights", "6. നിങ്ങളുടെ അവകാശങ്ങൾ",
     ["You can see and correct your own details and family members in the app at any time (My profile). You can choose your channels and whether your phone is in the directory.",
      "You can ask your club to correct or erase your data, to tell you what it holds about you, or to withdraw a consent you gave; the club must respond within the time the law allows. If the club does not, you may complain to the Data Protection Board of India.",
      "Children: family members under 18 are entered by their parent or guardian, who gives consent on their behalf."],
     ["ആപ്പിൽ (എന്റെ പ്രൊഫൈൽ) എപ്പോൾ വേണമെങ്കിലും സ്വന്തം വിവരങ്ങളും കുടുംബാംഗങ്ങളെയും കാണാനും തിരുത്താനും കഴിയും. ചാനലുകളും ഫോൺ ഡയറക്ടറിയിൽ വേണോ എന്നതും തിരഞ്ഞെടുക്കാം.",
      "നിങ്ങളുടെ ഡാറ്റ തിരുത്താനോ നീക്കം ചെയ്യാനോ, എന്തൊക്കെ സൂക്ഷിക്കുന്നുവെന്ന് അറിയിക്കാനോ, നൽകിയ സമ്മതം പിൻവലിക്കാനോ ക്ലബ്ബിനോട് ആവശ്യപ്പെടാം; നിയമം അനുവദിക്കുന്ന സമയത്തിനുള്ളിൽ ക്ലബ്ബ് മറുപടി നൽകണം. ഇല്ലെങ്കിൽ ഇന്ത്യയുടെ ഡാറ്റ സംരക്ഷണ ബോർഡിന് പരാതി നൽകാം.",
      "കുട്ടികൾ: 18 വയസ്സിൽ താഴെയുള്ള കുടുംബാംഗങ്ങളെ രക്ഷിതാവ് ചേർക്കുന്നു; അവർക്കു വേണ്ടി രക്ഷിതാവ് സമ്മതം നൽകുന്നു."]),
    ("7. Security", "7. സുരക്ഷ",
     ["Passwords are stored only as salted hashes. One-time codes expire in ten minutes and work once. Connections are encrypted (HTTPS). Sign-in and the public forms are rate-limited. Uploaded images are re-encoded and documents checked before they are stored. Every change by an office bearer is logged with the user and time.",
      "If a breach affecting your data ever occurs, the club and, where required, the Data Protection Board will be informed as the law requires."],
     ["പാസ്‌വേഡുകൾ സാൾട്ട് ചെയ്ത ഹാഷ് ആയി മാത്രം സൂക്ഷിക്കുന്നു. ഒറ്റത്തവണ കോഡുകൾ പത്ത് മിനിറ്റിൽ കാലഹരണപ്പെടും; ഒരിക്കൽ മാത്രം പ്രവർത്തിക്കും. കണക്ഷനുകൾ എൻക്രിപ്റ്റ് ചെയ്തത് (HTTPS). പ്രവേശനവും പൊതു ഫോമുകളും നിരക്ക് പരിമിതപ്പെടുത്തിയത്. അപ്‌ലോഡ് ചെയ്യുന്ന ചിത്രങ്ങൾ വീണ്ടും എൻകോഡ് ചെയ്യുന്നു; രേഖകൾ പരിശോധിക്കുന്നു. ഭാരവാഹികളുടെ ഓരോ മാറ്റവും ഉപയോക്താവും സമയവും സഹിതം രേഖപ്പെടുത്തുന്നു.",
      "നിങ്ങളുടെ ഡാറ്റയെ ബാധിക്കുന്ന ഒരു ലംഘനം ഉണ്ടായാൽ നിയമം ആവശ്യപ്പെടുന്നതുപോലെ ക്ലബ്ബിനെയും ആവശ്യമെങ്കിൽ ഡാറ്റ സംരക്ഷണ ബോർഡിനെയും അറിയിക്കും."]),
    ("8. Cookies and the installed app", "8. കുക്കികളും ഇൻസ്റ്റാൾ ചെയ്ത ആപ്പും",
     ["The app uses one cookie, for your sign-in session. It stores your language and theme choice on your device. There is no advertising or analytics tracking. The installed (home-screen) app caches screens on your device so they open quickly."],
     ["പ്രവേശന സെഷനുള്ള ഒരു കുക്കി മാത്രമേ ആപ്പ് ഉപയോഗിക്കൂ. ഭാഷയും തീമും നിങ്ങളുടെ ഉപകരണത്തിൽ സൂക്ഷിക്കുന്നു. പരസ്യമോ അനലിറ്റിക്സ് ട്രാക്കിംഗോ ഇല്ല. ഹോം സ്ക്രീനിൽ ഇൻസ്റ്റാൾ ചെയ്ത ആപ്പ് വേഗത്തിൽ തുറക്കാൻ സ്ക്രീനുകൾ ഉപകരണത്തിൽ കാഷ് ചെയ്യുന്നു."]),
    ("9. Changes", "9. മാറ്റങ്ങൾ",
     ["We may update this policy; the date at the top shows the current version. Material changes are announced in the app."],
     ["ഈ നയം ഞങ്ങൾ പുതുക്കിയേക്കാം; മുകളിലെ തീയതി നിലവിലെ പതിപ്പ് കാണിക്കുന്നു. പ്രധാന മാറ്റങ്ങൾ ആപ്പിൽ അറിയിക്കും."]),
]


def _fill(text, ctx):
    for k, v in ctx.items():
        text = text.replace("{" + k + "}", html.escape(v))
    return text


def render(kind, lang):
    from . import saas
    lang = lang if lang in ("en", "ml") else "en"
    pr = saas.product()
    ctx = {"product": pr["name"], "operator": pr["powered_by"].replace("Powered by ", "", 1) or pr["name"], "support": pr["support"] or "the contact in the app"}
    sections = TERMS if kind == "terms" else PRIVACY
    title = {"terms": ("Terms of service", "സേവന വ്യവസ്ഥകൾ"), "privacy": ("Privacy policy", "സ്വകാര്യതാ നയം")}[kind][0 if lang == "en" else 1]
    intro = {"terms": ("These terms apply to every club that uses {product} and to the people who use it on the club's behalf. The privacy policy, which explains how members' data is handled, is part of these terms.",
                       "{product} ഉപയോഗിക്കുന്ന എല്ലാ ക്ലബ്ബുകൾക്കും ക്ലബ്ബിനു വേണ്ടി അത് ഉപയോഗിക്കുന്നവർക്കും ഈ വ്യവസ്ഥകൾ ബാധകമാണ്. അംഗങ്ങളുടെ ഡാറ്റ എങ്ങനെ കൈകാര്യം ചെയ്യുന്നുവെന്ന് വിശദീകരിക്കുന്ന സ്വകാര്യതാ നയം ഈ വ്യവസ്ഥകളുടെ ഭാഗമാണ്."),
             "privacy": ("This policy explains what {product} stores about members and applicants, why, who can see it and what rights you have. It is written for members; the club's office bearers and the operator are bound by it.",
                         "{product} അംഗങ്ങളെയും അപേക്ഷകരെയും കുറിച്ച് എന്ത് സൂക്ഷിക്കുന്നു, എന്തിന്, ആർക്ക് കാണാം, നിങ്ങളുടെ അവകാശങ്ങൾ എന്തൊക്കെ എന്ന് ഈ നയം വിശദീകരിക്കുന്നു. അംഗങ്ങൾക്കു വേണ്ടി എഴുതിയത്; ക്ലബ്ബിന്റെ ഭാരവാഹികളും ഓപ്പറേറ്ററും ഇതിന് ബാധ്യസ്ഥരാണ്.")}[kind][0 if lang == "en" else 1]
    eff = dt.date.fromisoformat(EFFECTIVE)
    eff_s = eff.strftime("%d %B %Y") if lang == "en" else f"{eff.day}-{eff.month}-{eff.year}"
    body = [f"<h1>{html.escape(title)}</h1><p class='m'>{'Effective' if lang == 'en' else 'പ്രാബല്യത്തിൽ'}: {eff_s} · {html.escape(pr['name'])} · {html.escape(ctx['operator'])}</p>",
            f"<p>{_fill(intro, ctx)}</p>",
            f"<p class='m'><a href='/terms?lang={lang}'>{'Terms of service' if lang == 'en' else 'സേവന വ്യവസ്ഥകൾ'}</a> · <a href='/privacy?lang={lang}'>{'Privacy policy' if lang == 'en' else 'സ്വകാര്യതാ നയം'}</a> · <a href='/pricing?lang={lang}'>{'Pricing' if lang == 'en' else 'വില'}</a></p>"]
    for h_en, h_ml, p_en, p_ml in sections:
        body.append(f"<h2>{html.escape(h_ml if lang == 'ml' else h_en)}</h2>")
        for p in (p_ml if lang == "ml" else p_en):
            body.append(f"<p>{_fill(p, ctx)}</p>")
    body.append(f"<p class='m' style='margin-top:30px'>{'Contact' if lang == 'en' else 'ബന്ധപ്പെടുക'}: {html.escape(ctx['operator'])}{(' · ' + html.escape(pr['support'])) if pr['support'] else ''}</p>")
    return saas._page(lang, title, "<div class='legal'>" + "".join(body) + "</div>", "<style>.legal{max-width:760px}.legal h2{margin-top:22px}.legal p{margin:6px 0 10px}</style>")


@router.get("/terms", response_class=HTMLResponse)
def terms(lang: str = "en"):
    return render("terms", lang)


@router.get("/privacy", response_class=HTMLResponse)
def privacy(lang: str = "en"):
    return render("privacy", lang)

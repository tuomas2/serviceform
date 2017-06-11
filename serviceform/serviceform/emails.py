# -*- coding: utf-8 -*-
# (c) 2017 Tuomas Airaksinen
#
# This file is part of Serviceform.
#
# Serviceform is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Serviceform is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Serviceform.  If not, see <http://www.gnu.org/licenses/>.

from django.utils.translation import gettext_lazy as _

bulk_email_to_responsibles = _("""Dear {{responsible}},

Participation results for {{form}} are now available for you to view.
You can see all participants for the activities you are responsible of in the following URL:
{{url}}
From now on, you will also receive a notification message, if a new participation submitted to
the areas you are responsible of.You can also adjust your contact details and email notification
preferences from previously given URL.

Best regards,
Service form system administrators

Contact person:
{{contact}}""")


invite = _("""Dear {{participant}},

You are invited to participate in "{{ form }}".
You can fill in your participation details at {{ url }}.

Best regards,
Service form system administrators

Contact person:
{{contact}}""")

message_to_responsibles = _("""Dear {{responsible}},

New participation from {{participant}} has just been submitted to {{form}}.
You can see all participants for the activities you are responsible of in the following URL:
{{url}}
You can also adjust your contact details and email notification preferences from that URL.

Best regards,
Service form system administrators

Contact person:
{{contact}}""")

participant_new_form_revision = _("""Dear {{participant}},

New form revision to "{{ form }}" has been published.
Please update your participation information at {{ url }}.

Best regards,
Service form system administrators

Contact person:
{{contact}}""")

participant_on_finish = _("""Dear {{participant}},

You submitted form "{{ form }}" on {{ last_modified }}.
If you wish to change any of the details you gave, you can go to {{ url }}.

Best regards,
Service form system administrators

Contact person:
{{contact}}""")

resend_email_to_participants = _("""Dear {{participant}},

You submitted form "{{ form }}" on {{ last_modified }}.
If you wish to change any of the details you gave, you can go to {{ url }}.

Best regards,
Service form system administrators

Contact person:
{{contact}}""")

participant_on_update = _("""Dear {{participant}},

You submitted update to your data on form "{{ form }}" on {{ last_modified }}.
If you wish to change any of the details you gave, you can go to {{ url }}.

Best regards,
Service form system administrators

Contact person:
{{contact}}""")


request_responsible_auth_link = _("""Dear {{responsible}},

You can see all participants for the activities you are responsible of in the following URL:
{{url}}

Best regards,
Service form system administrators

Contact person:
{{contact}}""")


verification_email_to_participant = _("""Dear {{participant}},

Your email address needs to be verified. Please do so by clicking link below. Then you can
continue filling the form.

{{url}}

Best regards,
Service form system administrators

Contact person:
{{contact}}""")


# TODO: check this email content
email_to_member_auth_link = _("""Dear {{member}},

Here is your link to access your data in {{organization}}:
{{url}}

Best regards,
Service form system administrators

Contact person:
{{contact}}""")

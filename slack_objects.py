import json
import inspect
from datetime import datetime
import itertools
import requests

##########################################
# Utility functions
#


def _str_or_none(value: any) -> any:
    """will convert any value to string, except None stays None"""
    return None if value is None else str(value)


##########################################
# Base classes
#

class _Slack_Object:
    """Base class for all Slack objects"""
    
    def get_array(self) -> dict:        
        """returns the properties of an object as dict
        
        will not include properties that are None
        will call get_array() on relevant Slack objects
        """
        arr = dict()
        for key, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, list):
                    v_list = list()
                    for elem in value:
                        if isinstance(elem, (_Slack_Object)):
                            v_list.append(elem.get_array())
                        else:    
                            v_list.append(elem)
                    arr[key[1:]] = v_list
                else:
                    if isinstance(value, (_Slack_Object)):
                        arr[key[1:]] = value.get_array()            
                    else:    
                        arr[key[1:]] = value
        return arr

    def get_json(self) -> str:
        return json.dumps(self.get_array())
    
    def __eq__(self, other):
        """object can now be compared by value, including nested objects"""
        if not isinstance(other, type(self)):            
            return False    
        return all(
            self.__dict__[key1] == other.__dict__[key2] 
                for key1, key2 in zip(self.__dict__.keys(), other.__dict__.keys())
        )

    def __ne__(self, other):
        return not self.__eq__(other)


##########################################
# Message composition objects
#

class Text(_Slack_Object):
    """Text object used in Blocks"""
    TYPE_PLAIN_TEXT = "plain_text"
    TYPE_MRKDWN = "mrkdwn"
    TYPES = [TYPE_PLAIN_TEXT, TYPE_MRKDWN]

    def __init__(
            self, 
            text: str, 
            type: str = None,             
            emoji: bool = None, 
            verbatim:bool = None):
        #validations
        if type is None:
            type = self.TYPE_MRKDWN
        if type not in self.TYPES:
            raise ValueError(f"type must be one of: {json.dumps(self.TYPES)}")        
        if type != self.TYPE_PLAIN_TEXT and emoji is not None:
            raise ValueError(
                f"emoji can only be used with type {self.TYPE_PLAIN_TEXT}"
            )
        if emoji is not None and not isinstance(emoji, bool):
            raise TypeError("emoji must be of type bool")
        if verbatim is not None and not isinstance(verbatim, bool):
            raise TypeError("verbatim must be of type bool")
        #init        
        self._type = str(type)
        self._text = str(text)
        self._emoji = emoji
        self._verbatim = verbatim

    @property
    def text(self):
        return self._text

    @property
    def type(self):
        return self._type

    @property
    def emoji(self):
        return self._emoji

    @property
    def verbatim(self):
        return self._verbatim

    @classmethod
    def convert_n_validate(
            cls,
            text: any, 
            name: str, 
            max_length: int = None, 
            type = None):
        """converts str to Text if str or expects Text, checks type and length
        
        This function enables using str and Text to define text properties
        of many Blocks objects
        """
        if isinstance(text, str):
            text = cls(text, type)
        elif not isinstance(text, cls):
            raise TypeError(f"{name} must be either string or {cls}")        
        if type is not None and text.type != type:
            raise TypeError(f"{name} must be of type {type}")
        if max_length is not None and len(text.text) > max_length:
            raise ValueError(
                f"Maximum length of {name} is {max_length} characters"
                )        
        return text

        
class Option(_Slack_Object):
    def __init__(
            self, 
            text: any, 
            value: str, 
            url: str = None):
        #validations
        text = Text.convert_n_validate(text, "text", 75, Text.TYPE_PLAIN_TEXT)        
        value = str(value)
        if len(value) > 75:
            raise ValueError("Maximum length of value is 75 characters")        
        if url is not None:
            url = str(url)
            if  len(url) > 3000:
                raise ValueError("Maximum length of url is 3000 characters")
        #init
        self._text = text
        self._value = value
        self._url = url

    @property
    def text(self):
        return self._text

    @property
    def value(self):
        return self._value

    @property
    def url(self):
        return self._url

  
class ConfirmationDialog(_Slack_Object):
    def __init__(
            self, 
            title: any, 
            text: any, 
            confirm: any, 
            deny: any):
        #validations
        title = Text.convert_n_validate(
            title, 
            "title", 
            100, 
            Text.TYPE_PLAIN_TEXT
        )
        text = Text.convert_n_validate(
            text, 
            "text", 
            300
        )
        confirm = Text.convert_n_validate(
            confirm, 
            "confirm", 
            30, 
            Text.TYPE_PLAIN_TEXT
        )
        deny = Text.convert_n_validate(
            deny, 
            "deny", 
            30, 
            Text.TYPE_PLAIN_TEXT
        )        
        #init
        self._title = title
        self._text = text        
        self._confirm = confirm
        self._deny = deny

    @property
    def text(self):
        return self._text
    

class OptionGroup(_Slack_Object):
    def __init__(
            self, 
            label: any, 
            options: list):
        #validations
        label = Text.convert_n_validate(label, "label", 75, Text.TYPE_PLAIN_TEXT)
        if not isinstance(options, list):
            raise TypeError("options must be of type list")
        if len(options) > 100:
            raise ValueError("Maximum 100 options")
        if any(not isinstance(x, Option) for x in options):
            raise TypeError(
                "options must be of type Option"
            )

        #init
        self._label = label
        self._options = options        

    @property
    def label(self):
        return self._label

    @property
    def options(self):
        return self._options


##########################################
# Block Elements
#

class _BlockElement(_Slack_Object):
    def __init__(self, type: str):
        self._type = str(type)

    @property
    def type(self):
        return self._type


class ImageElement(_BlockElement):
    def __init__(
            self,
            image_url: str,
            alt_text: str):        
        super().__init__("image")
        image_url = str(image_url)
        if len(image_url) > 3000:
            raise ValueError(f"Maximum length of image_url is 3000 characters")
        alt_text = str(alt_text)
        if len(alt_text) > 2000:
            raise ValueError(f"Maximum length of alt_text is 2000 characters")  
        self._image_url = image_url
        self._alt_text = alt_text

    @property
    def image_url(self):
        return self._image_url

    @property
    def alt_text(self):
        return self._alt_text


class _InteractiveElement(_BlockElement):
    def __init__(
            self,
            type: str,
            action_id: str,
            confirm: ConfirmationDialog = None):
        super().__init__(type)
        # validations
        action_id = str(action_id)
        if len(action_id) > 255:
            raise ValueError("Maximum length of action_id is 255 characters")
        if confirm is not None and not isinstance(confirm, ConfirmationDialog):
            raise TypeError("confirm must be of type ConfirmationDialog")
        # init
        self._action_id = action_id
        self._confirm = confirm
    
    @property
    def action_id(self):
        return self._action_id
    
    @property
    def confirm(self):
        return self._confirm

class Button(_InteractiveElement):
    STYLE_PRIMARY = "primary"
    STYLE_DANGER = "danger"    
    STYLE_DEFAULT = None
    _STYLES_DEF = [STYLE_DANGER, STYLE_PRIMARY]

    def __init__(
            self, 
            text: any, 
            action_id: str, 
            url: str = None, 
            value: str = None,
            style:str = None,
            confirm: ConfirmationDialog = None):
        super().__init__("button", action_id, confirm)
        # validations
        text = Text.convert_n_validate(text, "text", 75, Text.TYPE_PLAIN_TEXT)
        if url is not None:
            url = str(url)
            if  len(url) > 3000:
                raise ValueError(f"Maximum length of url is 3000 characters")
        if value is not None: 
            value = str(value)
            if len(value) > 2000:
                raise ValueError(f"Maximum length of value is 2000 characters")
        if style is not None:
            style = str(style)
            if style not in self._STYLES_DEF:
                raise ValueError(f"invalid style")
        
        # init
        self._text = text        
        self._url = url
        self._value = value
        self._style = style

    @property
    def text(self):
        return self._text
    
    @property
    def url(self):
        return self._url

    @property
    def value(self):
        return self._value
    
    @property
    def style(self):
        return self._style

class _SelectMenuBase(_InteractiveElement):
    def __init__(
            self,                 
            type: str,             
            action_id: str,
            placeholder: any = None,
            confirm: ConfirmationDialog = None):
        super().__init__(type, action_id, confirm)
        #validation
        if placeholder is not None: 
            placeholder = Text.convert_n_validate(
                placeholder, 
                "placeholder", 
                150, 
                Text.TYPE_PLAIN_TEXT
            )
        # init
        self._placeholder = placeholder
        
    @property
    def placeholder(self):
        return self._placeholder


class SelectMenuStatic(_SelectMenuBase):
    _MAX_OPTIONS = 100
    _MAX_OPTION_GROUPS = 100

    def __init__(
            self,                 
            placeholder: any, 
            action_id: str, 
            options: list = None,
            option_groups: list = None,
            initial_option: Option = None,
            confirm: ConfirmationDialog = None):
        super().__init__(
            "static_select",             
            action_id, 
            placeholder, 
            confirm
        )
        #validations
        if options is not None:
            if not isinstance(options, list):
                raise TypeError("options need to be of type list")
            if len(options) > self._MAX_OPTIONS:
                raise ValueError(
                    f"Maximum number of options is {self._MAX_OPTIONS}"
                )
            if any(not isinstance(x, Option) for x in options):
                raise TypeError("options need to be of type Option")
            if any(x.url is not None for x in options):
                raise ValueError("url property in option not supported here")
        
        if option_groups is not None:
            if not isinstance(option_groups, list):
                raise TypeError("option_groups need to be of type list")
            if len(option_groups) > self._MAX_OPTION_GROUPS:
                raise ValueError(
                    f"Maximum {self._MAX_OPTION_GROUPS} in option_groups"
                )
            if any(not isinstance(x, OptionGroup) for x in option_groups):
                raise TypeError("option_groups need to be of type OptionGroup")

        if options is not None and option_groups is not None:
            ValueError("Only one of options, option_group can be specified")
        
        if initial_option is not None:
            if not isinstance(initial_option, Option):
                raise TypeError("initial_option must be of type Option") 
            if options is not None and not any(
                x == initial_option for x in options):
                raise ValueError(
                    "initial_option must be identical to an "
                        + "existing option in options"
                    )
            elif option_groups is not None:               
                all_options = list()
                for option_group in option_groups:
                    all_options += option_group.options
                if not any(x == initial_option for x in all_options):
                    raise ValueError(
                        "initial_option must be identical to an "
                            + "existing option in option_groups"
                        )
               
        #init
        self._options = options
        self._option_groups = option_groups
        self._initial_option = initial_option

    @property
    def options(self):
        return self._options

    @property
    def option_groups(self):
        return self._option_groups

    @property
    def initial_option(self):
        return self._initial_option


class SelectMenuExternal(_SelectMenuBase):
    def __init__(
            self,                 
            placeholder: any, 
            action_id: str, 
            initial_option: Option = None,
            min_query_length: int = None,
            confirm: ConfirmationDialog = None):
        super().__init__(
            "external_select", 
            action_id, 
            placeholder, 
            confirm
        )        
        self._initial_option = initial_option
        #validations
        if initial_option is not None and not isinstance(initial_option, Option):
            raise TypeError("initial_option must be of type Option") 
        if min_query_length is not None and min_query_length < 1:
            raise ValueError("min_query_length must be > 0")
        #init
        self._initial_option = initial_option
        self._min_query_length = min_query_length

    @property
    def initial_option(self):
        return self._initial_option

    @property
    def min_query_length(self):
        return self._min_query_length


class SelectMenuUsers(_SelectMenuBase):
    def __init__(
            self,                 
            placeholder: any, 
            action_id: str, 
            initial_user: str = None,                 
            confirm: ConfirmationDialog = None):
        super().__init__(
            "users_select", 
            action_id, 
            placeholder, 
            confirm
        )
        self._initial_user = _str_or_none(initial_user)

    @property
    def initial_user(self):
        return self._initial_user
       

class SelectMenuConversations(_SelectMenuBase):
    def __init__(
            self,                 
            placeholder: any, 
            action_id: str, 
            initial_conversation: str = None,                 
            confirm: ConfirmationDialog = None):
        super().__init__(
            "conversations_select", 
            action_id, 
            placeholder, 
            confirm
        )
        self._initial_conversation = _str_or_none(initial_conversation)

    @property
    def initial_conversation(self):
        return self._initial_conversation


class SelectMenuChannels(_SelectMenuBase):
    def __init__(
            self,                 
            placeholder: any, 
            action_id: str, 
            initial_channel: str = None,                 
            confirm: ConfirmationDialog = None):
        super().__init__(
            "channels_select", 
            action_id, 
            placeholder, 
            confirm
        )
        self._initial_channel = _str_or_none(initial_channel)

    @property
    def initial_channel(self):
        return self._initial_channel


class DatePicker(_SelectMenuBase):
    def __init__(
            self,
            action_id: str,
            placeholder: any = None,
            initial_date: str = None,
            confirm: ConfirmationDialog = None):        
        super().__init__(
            "datepicker", 
            action_id, 
            placeholder, 
            confirm
        )        
        if initial_date is not None:
            initial_date = str(initial_date)
            if len(initial_date) > 255:
                raise ValueError(
                    "Maximum length of initial_date is 255 characters"
                )
            try:
                datetime.strptime(initial_date, "%Y-%M-%d")
            except ValueError:
                raise ValueError(
                    "initial_date is not a valid date. Expecting: 'YYYY-MM-DD'"
                )
        
        self._initial_date = initial_date

    @property
    def initial_date(self):
        return self._initial_date


##########################################
# Layout Blocks
#

class _LayoutBlock(_Slack_Object):    
    def __init__(
            self, 
            type: str, 
            block_id: str = None):
        #validation
        type = str(type)
        if block_id is not None:
            block_id = str(block_id)
            if len(block_id) > 255:
                raise ValueError("Maximum length of block_id is 255 characters")
        #init
        self._type = type
        self._block_id = block_id

    @property
    def type(self):
        return self._type

    @property
    def block_id(self):
        return self._block_id


class Section(_LayoutBlock):        
    _MAX_FIELDS = 10    
    def __init__(
            self,             
            text: Text, 
            block_id: str = None,
            fields: list = None, 
            accessory: _BlockElement = None):
        super().__init__("section", block_id)
        if isinstance(text, str):
            text = Text(text)
        if not isinstance(text, Text):
            raise TypeError("text must be of type str or Text")
        if len(text.text) > 3000:
            raise ValueError("Maximum length of Text is 3000 characters")
        if fields is not None:
            if not isinstance(fields, list):
                raise TypeError("fields must be of type list")
            if len(fields) > self._MAX_FIELDS:
                raise ValueError(f"Max {self._MAX_FIELDS} elements in fields")
            # if all elements are str then convert them into Text objects
            if all(isinstance(x, str) for x in fields):                
                for i, field in enumerate(fields):
                    fields[i] = Text(fields[i], Text.TYPE_PLAIN_TEXT)
            if any(not isinstance(x, Text) for x in fields):
                raise TypeError("all elements in fields must be of type Text")
            if any(len(x.text) > 2000 for x in fields):
                raise TypeError(
                    "Maximum length for all texts in field is 2000 characters"
                )
        if accessory is not None and not isinstance(accessory, _BlockElement):
            raise TypeError("accessory must be a _BlockElement")
        
        self._text = text        
        self._fields  = fields
        self._accessory  = accessory
   
    @property
    def text(self):
        return self._text

    @property
    def fields(self):
        return self._fields

    @property
    def accessory(self):
        return self._accessory


class DividerBlock(_LayoutBlock):    
    def __init__(
            self,                         
            block_id: str = None):
        super().__init__("divider", block_id)
    

class ImageBlock(_LayoutBlock):    
    def __init__(
            self,             
            image_url: str, 
            alt_text: str, 
            title: any = None,
            block_id: str = None):
        super().__init__("image", block_id)        
        image_url = str(image_url)
        if len(image_url) > 3000:
            raise ValueError(f"Maximum length of image_url is 3000 characters")
        alt_text = str(alt_text)
        if len(alt_text) > 2000:
            raise ValueError(f"Maximum length of alt_text is 2000 characters")        
        if title is not None:
            title = Text.convert_n_validate(
                title, 
                "title", 
                2000, 
                Text.TYPE_PLAIN_TEXT
            )
        self._image_url = image_url
        self._alt_text = alt_text
        self._title  = title
    
    @property
    def image_url(self):
        return self._image_url

    @property
    def alt_text(self):
        return self._alt_text

    @property
    def title(self):
        return self._title


class ActionsBlock(_LayoutBlock):
    _MAX_ELEMENTS = 5
    def __init__(
            self, 
            elements: list, 
            block_id:str = None):
        super().__init__("actions", block_id)
        if not isinstance(elements, list):
            raise TypeError("elements must be of type list")
        if len(elements) > self._MAX_ELEMENTS:
            raise RuntimeError(
                f"Can not have more than {[self._MAX_ELEMENTS]} elements"
            )
        if any(not isinstance(x, _InteractiveElement) for x in elements):
            raise TypeError("all elements must be of type _InteractiveElement")
        self._elements = elements        

    @property
    def elements(self):
        return self._elements

    def add(self, element: _BlockElement) -> None:
        if not isinstance(element, _BlockElement):
            raise TypeError("element must be a _BlockElement")
        if len(self.elements) == self._MAX_ELEMENTS:
            raise RuntimeError(
                f"Can not have more than {[self._MAX_ELEMENTS]} elements"
            )
        self._elements.append(element)


class ContextBlock(_LayoutBlock):
    _MAX_ELEMENTS = 10
    def __init__(
            self, 
            elements: list, 
            block_id:str = None):
        super().__init__("context", block_id)
        if not isinstance(elements, list):
            raise TypeError("elements must be of type list")
        if len(elements) > self._MAX_ELEMENTS:
            raise RuntimeError(
                f"Can not have more than {[self._MAX_ELEMENTS]} elements"
            )
        if any(not isinstance(x, (Text, ImageElement)) for x in elements):
            raise TypeError("all elements must be of type Text or ImageElement")
        self._elements = elements
        self._block_id = block_id
    
    def add(self, element: _BlockElement) -> None:
        if not isinstance(element, _BlockElement):
            raise TypeError("element must be a _BlockElement")
        if len(self.elements) == self._MAX_ELEMENTS:
            raise RuntimeError(
                f"Can not have more than {[self._MAX_ELEMENTS]} elements"
            )
        self._elements.append(element)


class FileBlock(_LayoutBlock):    
    def __init__(
            self, 
            external_id: str,             
            block_id:str = None):
        super().__init__("file", block_id)        
        self._external_id = str(external_id)
        self._source = "remote"
    

##########################################
# Blocks container
#

class Blocks(_Slack_Object):
    def __init__(self, layout_blocks: list = None):
        layout_blocks = list() if layout_blocks is None else layout_blocks
        if any(not isinstance(x, _LayoutBlock) for x in layout_blocks):
            raise TypeError(
                "elements of layout_block must be of type _LayoutBlock"
            )
        self._blocks = layout_blocks
    
    def get_array(self):
        arr = list()
        for layout_block in self._blocks:
            arr.append(layout_block.get_array())
        return arr

    def append(self, layout_block: _LayoutBlock):
        if not isinstance(layout_block, _LayoutBlock):
            raise TypeError("layoutout block must be of type _LayoutBlock")
        else:
            self._blocks.append(layout_block)
                

##########################################
# Message objects
#

class Message(_Slack_Object):
    """Message paylout object for Slack
    
    Note that Blocks are fully supported with class wrappers by this library
    but attachments are not. So attachment objects need to be build manually.
    """
    def __init__(
            self,
            text: str = None,
            blocks: Blocks = None,
            attachments: list = None,
            thread_ts: str = None,
            mrkdwn: bool = None):
        # validation
        if text is not None:
            text = str(text)
        if blocks is not None and not isinstance(blocks, Blocks):
            raise TypeError("blocks must be of type Blocks")
        if attachments is not None and not isinstance(attachments, list):
            raise TypeError("attachments must be of type list")
        if thread_ts is not None:
            thread_ts = str(thread_ts)
        if mrkdwn is not None and not isinstance(mrkdwn, bool):
            raise TypeError("mrkdwn must be of type bool")
        if text is None and blocks is None and attachments is None:
            raise ValueError(
                "One of these have to provided: text, blocks, attachments"
            )
        # init
        self._text = text
        self._blocks = blocks
        self._attachments = attachments
        self._thread_ts = thread_ts
        self._mrkdwn = mrkdwn

    @property
    def text(self):
        return self._text

    @property
    def blocks(self):
        return self._blocks

    @property
    def attachments(self):
        return self._attachments

    @property
    def thread_ts(self):
        return self._thread_ts

    @property
    def mrkdwn(self):
        return self._mrkdwn


class ResponseMessage(Message):
    """ResponseMessage object used for responding to Slash requests

    Can be used to respond to slash commands, interactive requests and actions
    either directly to the request or by sending it to the provided request url
    """
    TYPE_EPHEMERAL = "ephemeral"
    TYPE_IN_CHANNEL = "in_channel"
    _TYPES_DEF = [TYPE_EPHEMERAL, TYPE_IN_CHANNEL]
    
    def __init__(
            self,
            text: str = None,
            blocks: str = None,
            attachments: list = None,
            mrkdwn: bool = None,
            response_type: str = None,
            delete_original: bool = None,
            replace_original: bool = None):        
        super().__init__(
            text=text, 
            blocks=blocks, 
            attachments=attachments, 
            thread_ts=None, 
            mrkdwn=mrkdwn
        )       
        self.response_type = response_type
        self.delete_original = delete_original
        self.replace_original = replace_original
        
    @property
    def response_type(self):
        return self._response_type

    @response_type.setter
    def response_type(self, value: str) -> None:
        if value is not None and value not in self._TYPES_DEF:            
            raise ValueError(
                "valid values for response_type are: " 
                    + ', '.join(self._TYPES_DEF)
            )
        self._response_type = value

    @property
    def delete_original(self):
        return self._delete_original

    @delete_original.setter
    def delete_original(self, value: bool) -> None:
        if value is not None and not isinstance(value, bool):
            raise TypeError("delete_original must be of Type bool")
        self._delete_original = value

    @property
    def replace_original(self):
        return self._replace_original
    
    @replace_original.setter
    def replace_original(self, value: bool) -> None:
        if value is not None and not isinstance(value, bool):
            raise TypeError("replace_original must be of Type bool")
        self._replace_original = value

    def send(self, response_url: str):
        res = requests.post(response_url, json=self.get_array())
        res.raise_for_status()


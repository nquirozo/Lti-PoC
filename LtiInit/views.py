from django.http.response import JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
from pylti1p3.contrib.django import DjangoDbToolConf, DjangoOIDCLogin, DjangoMessageLaunch, DjangoCacheDataStorage 
from pylti1p3.exception import OIDCException, LtiException
from pylti1p3.tool_config import ToolConfJsonFile
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.lineitem import LineItem
from pylti1p3.grade import Grade
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from pprint import pprint
import os
import json
import datetime

#Al parecer en la plataforma de salti hay problemas tambien
class ExtendedDjangoMessageLaunch(DjangoMessageLaunch):
    def validate_nonce(self):
        """
        Probably it is bug on "https://lti-ri.imsglobal.org":
        site passes invalid "nonce" value during deep links launch.
        Because of this in case of iss == http://imsglobal.org just skip nonce validation.
        """
        iss = self.get_iss()
        deep_link_launch = self.is_deep_link_launch()
        if iss == "https://saltire.lti.app/platform":
            return self
        #si no es la plataforma de test se valida el nonce
        return super(ExtendedDjangoMessageLaunch, self).validate_nonce()


        
def get_launch_url(request):
    target_link_uri = request.POST.get('target_link_uri', request.GET.get('target_link_uri'))
    if not target_link_uri:
        raise Exception('Missing "target_link_uri" param')
    return target_link_uri

@require_POST
@csrf_exempt
def login(request):
    try:
        tool_conf = get_tool_conf()
        oidc_login = DjangoOIDCLogin(request, tool_conf)
        return oidc_login.redirect(get_launch_url(request))    
    except OIDCException:
        # display error page
        print('Error doing OIDC login')


@csrf_exempt
def launch(request):
    try:
        tool_conf = get_tool_conf()
        launch_data_storage = get_launch_data_storage()
        message_launch = ExtendedDjangoMessageLaunch(request, tool_conf, launch_data_storage=launch_data_storage)
        launch_data = message_launch.get_launch_data()
        pprint(launch_data)
        if message_launch.is_resource_launch():
            return render(request, 'resource.html', {
                'launch_data':launch_data,
                'roles': launch_data["https://purl.imsglobal.org/spec/lti/claim/roles"],
                'nombre': launch_data["name"]
                })
        elif message_launch.is_deep_link_launch():
            return deeplink(request, message_launch)
        else:
            print("Unknown launch type")
    except LtiException as e:
        print(e)
        print('Launch validation failed')
    return HttpResponse('hola mundo')


def get_lti_config_path():
    return os.path.join(settings.BASE_DIR, 'config', 'config.json')


def get_tool_conf():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    return tool_conf


def get_launch_data_storage():
    return DjangoCacheDataStorage()

def deeplink(request, message_launch):
    print("Deep Linking Launch!")
    launch_id = message_launch.get_launch_id()
    deep_link = message_launch.get_deep_link()
    resource = DeepLinkResource()
    resource.set_url("http://127.0.0.1:8000/lti/dpl")\
            .set_title("Lti Test app")
    response = deep_link.get_response_jwt([resource])
    if message_launch.has_cgs():
        print("Has cgs")
        cgs = message_launch.get_cgs()
        # Get all available groups
        groups = cgs.get_groups()

    if message_launch.has_ags():
        print("Has Assignments and Grades Service")
        #obtiene assigments and grades
        ags = message_launch.get_ags()
        #obtengo todos los lineitems
        items_lst = ags.get_lineitems()
        #busco el primer lineitem
        item = ags.find_lineitem_by_id(items_lst[0]["id"])
        grades = ags.get_grades(item)
        

    if message_launch.has_nrps():
        print("Has Names and Roles Service")
        nrps = message_launch.get_nrps()
        members = nrps.get_members()
    launch_data = message_launch.get_launch_data()
    return render(request, 'deeplinking.html', {
                'launch_data':launch_data,
                'roles': launch_data["https://purl.imsglobal.org/spec/lti/claim/roles"],
                'nombre': launch_data["name"],
                'members': members,
                'launch_id':launch_id
                })
@require_POST
@csrf_exempt
def creaNota(request):
    post_data = json.loads(request.body.decode("utf-8"))

    launch_id = post_data.get("launch_id")
    tool_conf = get_tool_conf()
    launch_data_storage = get_launch_data_storage()
    message_launch = ExtendedDjangoMessageLaunch.from_cache(launch_id, request, tool_conf,
                                                            launch_data_storage=launch_data_storage)
    
    if not message_launch.has_ags():
        raise "No ags"
    ags = message_launch.get_ags()

    line_item = LineItem()
    line_item.set_tag(post_data.get("tag"))\
        .set_score_maximum(float(post_data.get("scoreMax")))\
        .set_label(post_data.get("label"))\
        .set_resource_id("maqueta_lti")
    #no se si se ocupan los valores label y resource_id .

    timestamp = datetime.datetime.utcnow().isoformat() + 'Z'    

    sc = Grade()
    sc.set_score_given(float(post_data.get("nota")))\
        .set_score_maximum(float(post_data.get("scoreMax")))\
        .set_timestamp(timestamp)\
        .set_activity_progress('Completed')\
        .set_grading_progress('FullyGraded')\
        .set_user_id(post_data.get("user_id"))
    ags.put_grade(sc, line_item)

    return HttpResponse(201)


@require_GET
def ObtenerNotas(request):

    launch_id = request.GET.get("launch_id")
    tag = request.GET.get("tag")
    tool_conf = get_tool_conf()
    launch_data_storage = get_launch_data_storage()
    message_launch = ExtendedDjangoMessageLaunch.from_cache(launch_id, request, tool_conf,
                                                            launch_data_storage=launch_data_storage)
    
    if not message_launch.has_ags():
        raise "No ags"

    ags = message_launch.get_ags()

    notas_tag = ags.find_lineitem_by_tag(tag)

    grades = ags.get_grades(notas_tag)

    return JsonResponse(grades, safe=False)


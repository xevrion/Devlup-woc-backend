import random
from fastapi import APIRouter, Depends,HTTPException,Query
from fastapi import  Request, Header
from jsonschema import ValidationError
from models.Timeline import Timeline
from models.Project import Project
from models.Idea import Idea
from models.User import User
from models.Mentor import Mentor
from models.Proposal import Proposal
from models.Admin import Admin
from models.ProjectList import ProjectSummaryInput
from config.database import collection_projects
from config.database import collection_timeline,collection_mentors,collection_ideas,collection_programs,collection_proposals,collection_progress
from config.database import collection_users
from starlette.requests import Request  
from google.auth.transport import requests
from fastapi.responses import JSONResponse
from bson import ObjectId
from dotenv import load_dotenv
from typing import Annotated, Dict, List
from routes.auth import create_access_token, get_current_user,get_current_user_role,role_required

load_dotenv()  
import os
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET =os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")
import requests
route = APIRouter()
woc_status = True
results=False

#projects 
@route.post('/project', dependencies=[Depends(role_required(["scrummaster"]))])
async def add_project(request: Request):
    data = await request.json()
    project_id = ''.join(random.choices('0123456789', k=5))
    data["id"] = project_id 
    project = Project(**data)
    collection_projects.insert_one(project.dict())
    return {"success": True, "project_id": project_id}
@route.get("/mentor_projects/{mentorid}", response_model=List[Project])
async def fetch_projects_by_mentor_id(mentorid: str):
    projects = list(collection_projects.find({"mentorid": mentorid}))
    if not projects:
        raise HTTPException(status_code=404, detail="No projects found for this mentor ID")
    return [Project(**project) for project in projects]
@route.put('/update_project/',dependencies=[Depends(role_required(["scrummaster"]))])
async def update_project(request:Request):
    data=await request.json()
    id = data['id']
    link =data['link']
    project = collection_projects.find_one({"id": id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = collection_projects.update_one(
        {"id": id},
        {
            "$set": 
         {
            "completed": True,
            "codelink": link
        }
         }
    )
    projects_data = list(collection_projects.find({"completed": False}))
    projects = [
    Project(**project) for project in projects_data
]
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update the project")
    
    return {"message": "Project updated successfully", "id": id,"projects":projects}

@route.post("/check-duplicate-username")
async def check_duplicate_username(request: Request):
    data = await request.json()
    existing_user = collection_users.find_one({
        "first_name": data["first_name"],
        "last_name": data["last_name"]
    })

    if existing_user:
        raise HTTPException(status_code=400, detail="Already someone has the same username.")
    return {"message": "Username is available."}
@route.get('/projects')
async def get_projects():
    projects_data = list(collection_projects.find({"completed": False}))
    projects = [
    Project(**project) for project in projects_data
]
    return projects

#timeline
@route.get('/timeline', response_model=Dict[str, List[Timeline]])
async def get_timeline():
    timelines = []
    
    for timeline in collection_timeline.find({}):
        events = timeline.get("events", [])
        timelines.append(
            Timeline(
                id=str(timeline["_id"]),
                date=str(timeline["date"]),
                events=events,
                completed=timeline.get("completed", False)
            )
        )
    
    return {"timelines": timelines}

@route.post('/timeline',dependencies=[Depends(role_required(["scrummaster"]))])
async def post_timeline(request:Request):
    try:
        data = await request.json()
        data['id'] = str(random.randint(1000, 9999))
        timeline = Timeline(**data)
        collection_timeline.insert_one(timeline.dict())
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
 
@route.put('/updatetimeline/{id}/{done}',dependencies=[Depends(role_required(["scrummaster"]))])
async def update_timeline(id:str,done:bool):
 collection_timeline.update_one(
    {"_id": ObjectId(id)},

    {"$set": {"completed": done}}  
 )
 return{'status':'success'}
 
    
#google authentication
@route.post("/auth/google")
async def auth_google(request:Request):
    data = await request.json()
    code = data['code']
    token_url = "https://accounts.google.com/o/oauth2/token"
    
    data = {
        "code": code,
        "client_id": {GOOGLE_CLIENT_ID},
        "client_secret":{GOOGLE_CLIENT_SECRET},
        "redirect_uri": {GOOGLE_REDIRECT_URI},
        "grant_type": "authorization_code",
        "expires_in": 86400
    }
    response = requests.post(token_url, data=data)
    resp=  response.json()
    access_token=resp.get("access_token")
    refresh_token = resp.get("refresh_token")
    if(access_token):
        user_info = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        print(user_info.json())
        email = user_info.json().get("email")
        if email and email.endswith("@iitj.ac.in"):
             token = create_access_token({"role":"1","id":user_info.json().get("id")})
             return {"success":True, "user":user_info.json(),"token":access_token,"refresh":refresh_token,"jwt_token":token}
        else:
            return {
                "success": False,
                "message": "Email must end with @iitj.ac.in"
            }
    else:
        return {
            "success": False,
            "message": "Failed to obtain access token"
        }
   
# WOC Status
@route.get("/woc_status")
async def wocstatus(request:Request):
      global woc_status
      print(woc_status)
      return woc_status
   
@route.put("/changestatus",dependencies=[Depends(role_required(["scrummaster"]))])
async def change_status(request:Request):
      global woc_status
      woc_status=not woc_status
      print(woc_status)
      return woc_status
#results
@route.get("/results")
async def resultstatus(request:Request):
      global results
      print(results)
      return results
   
@route.put("/changeresult",dependencies=[Depends(role_required(["scrummaster"]))])
async def change_status(request:Request):
      global results
      results=not results
      print(results)
      return results
#token verification
@route.get("/token")
async def get_user( 
    access_token: Annotated[str | None, Header()] = None,
    refresh_token: Annotated[str | None, Header()] = None): 
    data = {
        "client_id": {GOOGLE_CLIENT_ID},
        "client_secret": {GOOGLE_CLIENT_SECRET},
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    try:
     user_info = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"})
     response = requests.post("https://oauth2.googleapis.com/token", data=data)
     response_data = response.json()
     if response.ok:
        access_token = response_data["access_token"]
     else:
        return {"success":False}
     getuser=user_info.json()

     if getuser is None or 'id' not in getuser:
      user_info = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"})
      getuser = user_info.json()
     user=collection_users.find_one({'id':getuser["id"]})
     user =     User(**user)
     user=user.dict()

     jwt_token = create_access_token({"role":user['role'],"id":user['id']})
     user_with_image = {**user, "image": getuser["picture"]}
  
     return {"success":True, 'user':user_with_image,"access_token":access_token,"jwt_token":jwt_token}
    
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}

#edit_timeline
@route.post("/")
async def edit_timeline(request:Request):
    data = await request.json()
    status = data.status
    Id = data.id
    id = ObjectId(Id)
    item = collection_timeline.find_one({"_id": id})
    new_values = {"$set": {"date": item.date, "events": item.events,"completed":status}}
    collection_timeline.update_one({"_id": id}, new_values)

#user
@route.post("/user")
async def create_user(request:Request,token_data: dict = Depends(get_current_user)):
    if token_data.get('id') is None:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to create user for this token",
        )

    data = await request.json()
    user = User(**data)
    collection_users.insert_one(user.dict())
    token = create_access_token({"role":user.role,"id":user.id})
    return{"success":"true","jwt_token":token}

@route.get("/userinfo/{id}")
async def get_user(id:str,token_data: dict = Depends(get_current_user)):
    if(token_data['id']==None):
       raise HTTPException(
            status_code=403,
            detail="Unauthorized user",
        )
    user =collection_users.find_one({'id':id})
    if(user):
     user = User(**user)
     user=user.dict()
     token = create_access_token({"role":user["role"],"id":user["id"]})
     return {"success":"true",'user':user,"token":token}
    else :
     return{"success":'false'}

@route.put("/updateuser")
async def update_user(request:Request,token_data: dict = Depends(get_current_user)):
   
   resp = await request.json()
   data= resp['updateduser']
   if data["id"] != token_data["id"]:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to delete proposal for this user",
        )
   user = collection_users.find_one({"id": data['id']})
   if user is None:
      return{"success":"false","error":"user is not found"}
   else :
      update_user = User(**data)
      collection_users.update_one(
        {"_id": user["_id"]}, 
        {"$set": update_user.dict()}  
    )
   return {"success":'true',"update_user":update_user.dict()}

#mentor
@route.post("/tobementor",dependencies=[Depends(role_required(["1"]))])
async def request_mentor(request:Request):
   resp = await request.json()
   user = collection_mentors.find_one({"id":resp["id"]})
   if(user):
      return{"success":False,'msg':"You have already sent your request."}
   else:
    mentor = Mentor(**resp)
    collection_mentors.insert_one(mentor.dict())
    return{"success":True,'msg':"Successfully sent request"}

@route.post("/acceptmentor",dependencies=[Depends(role_required(["scrummaster"]))])
async def acceptmentor(request:Request,):
    resp = await request.json()
    collection_users.update_one(
        {"id": resp['id']}, 
        {"$set": {
            "role": "2",
        }}  )
    collection_mentors.delete_one({"id":  resp["id"]})
    return{"success":"true"}
   
@route.get("/getrequests",dependencies=[Depends(role_required(["scrummaster"]))])
async def getmentor_requests():
    mentors = collection_mentors.find()
    return [Mentor(**mentor) for mentor in mentors]

@route.get("/allmentors")
async def getmentors():
   mentors = collection_users.find({'role':'2'})
   mentors = [User(**mentor) for mentor in mentors]
   return mentors
#ideas
@route.post("/idea")
async def create_idea(request:Request,token_data: dict = Depends(get_current_user)):
   try:
    if(token_data['id']==None):
       raise HTTPException(
            status_code=403,
            detail="Unauthorized user",
        )
    resp = await request.json()
    idea = Idea(**resp)
    collection_ideas.insert_one(idea.dict())
    return {'success':'true'}
   except requests.exceptions.RequestException as e:
    return {"success": False, "error": str(e)}
@route.get("/idea",dependencies=[Depends(role_required(["scrummaster"]))])
async def getallideas():
    ideas = list(collection_ideas.find())
    return [Idea(**idea) for idea in ideas]
    


@route.get("/pastprograms")
async def getpastprograms():
    programs = list(collection_projects.find({"completed": True}))
    pastprojects = [
    Project(**project) for project in programs
]
    return pastprojects


#addsprojects
@route.post("/users/project")
async def append_project_to_user(request: Request,token_data: dict = Depends(get_current_user)):
    resp = await request.json()
    user_id = resp["user"]
    project_id = resp["_id"]
    if user_id != token_data["id"]:

        raise HTTPException(
            status_code=403,
            detail="Unauthorized to delete proposal for this user",
        ) 
    user = collection_users.find_one({"id": user_id})
    if user is None:
        raise HTTPException(status_code=404, detail="User not found", success=False)
        
    user = User(**user)  
    user=user.dict()
    if len(user["projects"]) >= 2:
        return {"success": False, 'msg': "Already applied for two projects"}
    
    project = collection_projects.find_one({"id": project_id})
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    updated_user = collection_users.update_one(
        {"id": user_id},
        {"$addToSet": {"projects": project}}
    )
    user = collection_users.find_one({"id":user_id})
    user = User(**user)
    proposal = resp["proposal"]
    print(proposal)
    proposal['id'] = str(random.randint(1000, 9999))
    proposal=Proposal(**proposal)
    collection_proposals.insert_one(proposal.dict())
    return {"msg": "Project appended to user successfully","proposal":proposal.dict(),"user":user.dict()}
@route.get("/{user_id}/projects")
async def user_projects(user_id:str,token_data: dict = Depends(get_current_user)):
   if user_id != token_data["id"]:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to delete proposal for this user",
        )    
   user = collection_users.find_one({"id":user_id})  
   projects = [Project(**project) for project in user["projects"]]
   return projects

#proposal
route.post("/addproposal")
async def addproposal(request:Request):
   data = await request.json()
   proposal = collection_proposals.insert_one(data)
   proposal = Proposal(**proposal)
   return{"success":"true","proposal":proposal}
@route.get("/allproposals",dependencies=[Depends(role_required(["scrummaster"]))])
async def allproposals():
   proposals = collection_proposals.find({})
   proposals = [Proposal(**proposal) for proposal in proposals]
   return proposals

@route.delete("/deleteproposal")
async def deleteproposal(user_id: str = Query(...), title: str = Query(...),id:str = Query(...),token_data: dict = Depends(get_current_user)
):
   user_id = (user_id)
   if user_id != token_data["id"]:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to delete proposal for this user",
        )
   collection_users.update_one(
        {'id':user_id},  
        {'$pull': {'projects': {'title':title}}}, 
    )
   user = collection_users.find_one({"id":user_id})
   user = User(**user)
   email = user.email
   result = collection_proposals.delete_one({"title": title, "email": email})
   if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Proposal not found")
   return{"success":"true","msg":"Deleted proposal","user":user.dict()}

@route.put('/updateproposal/{id}/{done}/{mentorid}')
async def update_proposal(id: str, done: bool, mentorid: str, token_data: dict = Depends(get_current_user)):
    if mentorid != token_data["id"]:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to update proposal for this user",
        )
    proposal = collection_proposals.find_one({"id": id})
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    collection_proposals.update_one(
        {"id": id},
        {"$set": {"status": done}}
    )
    project = collection_projects.find_one({"title": proposal['title']})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if done:
        if proposal['name'] not in project['mentee']:
            project['mentee'].append(proposal['name'])
    else:  
        if proposal['name'] in project['mentee']:
            project['mentee'].remove(proposal['name'])

    collection_projects.update_one(
        {"id": project['id']},
        {"$set": {"mentee": project['mentee']}}
    )

    return {'status': 'success'}

@route.get("/proposals/{mentorid}")
async def getproposals(mentorid:str,token_data: dict = Depends(get_current_user)):
   if mentorid!= token_data["id"]:
        raise HTTPException(
            status_code=403,
            detail="Unauthorized to delete proposal for this user",
        )
   proposals = collection_proposals.find({"mentorid":mentorid})
   proposals = [Proposal(**proposal) for proposal in proposals]
   return proposals

#progress
@route.post("/addprogress",dependencies=[Depends(role_required(["2"]))])
async def update_project_progress(request:Request):
    try:
        data= await request.json()
        result = collection_projects.update_one(
            {"id": data["id"]},
            {"$set": {"progress": data["progress"]}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Project not found")

        return {"message": "Progress updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@route.get("/get_max_project_count")
async def get_max_project_count():
    return {"max_project_count": Admin.max_project_count}

@route.put("/set_max_project_count",dependencies=[Depends(role_required(["scrummaster"]))])
async def set_max_project_count(request: Request):
    data = await request.json()
    Admin.max_project_count = data["max_project_count"]
    return {"max_project_count": Admin.max_project_count}

@route.post("/project/summary")
async def create_project_summary(summary: ProjectSummaryInput):
    document = {
        "title": summary.proj_name,
        "mentors": summary.mentor_name,
        "linkedin_link": summary.linkedin,
        "github_link": summary.github
    }

    result = collection_projects.insert_one(document)   # Mongo auto _id

    # Convert ObjectId → string
    inserted_id = str(result.inserted_id)

    return {
        "success": True,
        "message": "Project summary added successfully",
        "id": inserted_id
    }

@route.get("/project/summary")
async def get_project_summary():
    projects = list(collection_projects.find({}))

    result = []
    for proj in projects:
        _id = proj.get("_id")

        # Convert ObjectId to string
        if isinstance(_id, ObjectId):
            _id = str(_id)

        result.append({
            "id": _id,
            "proj_name": proj.get("title"),
            "mentor_name": proj.get("mentors", []),
            "linkedin": proj.get("linkedin_link", []),
            "github": proj.get("github_link", [])
        })

    return result

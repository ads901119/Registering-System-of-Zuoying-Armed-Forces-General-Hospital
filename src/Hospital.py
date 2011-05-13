# -*- coding: utf-8 -*-
from google.appengine.api import taskqueue
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from django.utils import simplejson as json
from BeautifulSoup import BeautifulSoup
import datetime
import urllib
import urllib2
import httplib
import re
import cookielib

class Department(db.Model):
    id = db.IntegerProperty(required=True)
    name = db.StringProperty(required=True)
    SectNO = db.StringProperty() # defined by the hospital
    doctors = db.StringListProperty()

class Doctor(db.Model):
    id = db.IntegerProperty(required=True)
    name = db.StringProperty(required=True)
    EmpNO = db.StringProperty() # defined by the hospital
    department = db.StringProperty(required=True)

class Hello(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        operations = [r'/fetchData', r'/listDatabase', r'/clearDatabase',
                      r'/dept', r'/doctor', r'/register', r'/cancel_register']
        self.response.out.write('Available Operations:\n' + json.dumps(operations) + '\n\n')
        self.response.out.write('Registration example:\nregister?doctor=41&dept=14&time=2011-05-14-A&id=E124068750&birthday=1989-09-14\n\n')
        self.response.out.write('Cancel Registration example:\ncancel_register?doctor=41&dept=14&time=2011-05-14-A&id=E124068750&birthday=1989-09-14\n\n')

class FetchData(webapp.RequestHandler):
    def post(self):
        # for enumerating doctors of a department
        rootUrl = "http://806.mnd.gov.tw/index.php?page=hospital_02&doctor=doctor&drp_id="
        
        # for enumerating departments 
        url = "http://806.mnd.gov.tw/index.php?page=hospital_02"

        request = urllib2.Request(url)
        request.add_header('User-Agent', 'Mozilla 5.0')
        page = urllib2.urlopen(request)
        soup = BeautifulSoup(page, fromEncoding='utf-8')
        
        # departments
        selectDepts = soup.find("select")
        
        # fetch sectNo & empNo
        conn = httplib.HTTPConnection("806.mnd.gov.tw",8080)
        headers = {
                       "User-Agent": "Mozilla/5.0",
                       "Connection": "keep-alive",
                       "Content-Type": "application/x-www-form-urlencoded"
                  }
        conn.request("GET", url="/register/stepB1.asp", headers=headers)
        response = conn.getresponse()
        data = response.read()
        soup = BeautifulSoup(data, fromEncoding='big5')
        selectSectNO = soup.find('select', {'id': 'SectNO'})
        selectEmpNO = soup.find('select', {'id': 'EmpNO'})
        SectNO = dict([(unicode(option.string), option['value']) 
                       for option in selectSectNO('option')])
        EmpNO = dict([(unicode(option.string), option['value']) 
                      for option in selectEmpNO('option')])
        
        # build database
        deptId = 1
        doctId = 1
        for deptTag in selectDepts('option')[1:]:
            
            departmentName = unicode(deptTag.string)
            
            link = rootUrl + deptTag['value']
            request = urllib2.Request(link)
            request.add_header('User-Agent', 'Mozilla 5.0')
            page = urllib2.urlopen(request)
            soup2 = BeautifulSoup(page, fromEncoding='utf-8')
            
            doctorTags = soup2.findAll('a', "blue_15_a")
            doctors = [unicode(doctorTag.string) for doctorTag in doctorTags]
            
            try: 
                SectNOEntry = SectNO[departmentName]
            except:
                # Department list of the dept. introduction page 
                # does not match with the registration page
                SectNOEntry = ''
            dept = Department(id = deptId,
                              name = departmentName,
                              SectNO = SectNOEntry,
                              doctors = doctors)
            dept.put()
            deptId += 1
            
            for doctor in doctors:
                try:
                    EmpNOEntry = EmpNO[doctor]
                except:
                    # Doctor list of the doctor introduction page 
                    # does not match with the registration page
                    EmpNOEntry = ''
                doct = Doctor(id = doctId,
                              name = doctor,
                              EmpNO = EmpNOEntry,
                              department = departmentName)
                doct.put()
                doctId += 1

        self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        self.response.out.write('This page is used to renew database')
        
class ListDatabase(webapp.RequestHandler):
    def get(self):
        q = Department.all()
        q.order("id")
        
        # The query is not executed until results are accessed.
        results = q.fetch(1000)
        str = 'Department:\n'
        for d in results:
            str += "%(id)3d %(SectNO)s %(name)s: " \
                    % {'id': d.id, 'SectNO': d.SectNO, 'name': d.name}
            for doctor in d.doctors:
                str += "%s " % doctor
            str += '\n'
        
        str += '\nDoctors:\n'
        q = Doctor.all()
        q.order("id")
        results = q.fetch(1000)
        for d in results:
            str += "%(id)3d %(EmpNO)s %(name)s %(dept)s\n" \
                    % {'id': d.id, 'EmpNO': d.EmpNO, 'name': d.name, 'dept': d.department}
        
        self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        self.response.out.write(str)

class ClearDatabase(webapp.RequestHandler):
    def get(self):
        q = Department.all()
        results = q.fetch(1000)
        for result in results:
            result.delete()
        
        q = Doctor.all()
        results = q.fetch(1000)
        for result in results:
            result.delete()
        
        self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        self.response.out.write('Clear Database')

class Departments(webapp.RequestHandler):
    def get(self):
        queryId = self.request.get('id')
        if queryId == '': # return all departments
            q = Department.all()
            q.order("id")
            
            # The query is not executed until results are accessed.
            results = q.fetch(1000)
            ret = []
            for d in results:
                ret += [{d.id: d.name}]
        else:
            queryId = int(queryId)
            headers = {
                           "User-Agent": "Mozilla/5.0",
                           "Connection": "keep-alive",
                           "Content-Type": "application/x-www-form-urlencoded"
                      }
            q = Department.all()
            q.filter("id =", queryId)
            results = q.fetch(1)
            try:
                result = results.pop()
            except:
                self.response.out.write(json.dumps([], ensure_ascii=False, indent=4))
                return
            
            departmentName = result.name
            EmpNO = ''
            SectNO = result.SectNO
            fromDate = datetime.date.today()
            toDate = fromDate + datetime.timedelta(7)
            
            syear = str(fromDate.year - 1911)
            smonth = '%02d' %  fromDate.month
            sday = '%02d' % fromDate.day
            eyear = str(toDate.year - 1911)
            emonth = '%02d' % toDate.month
            eday = '%02d' % toDate.day
            
            params = urllib.urlencode({
                          'syear': syear, 'smonth': smonth, 'sday': sday,
                          'eyear': eyear, 'emonth': emonth, 'eday': eday,
                          'SectNO': SectNO, 'EmpNO': EmpNO, 'isQuery': '1'
                     })
            
            conn = httplib.HTTPConnection("806.mnd.gov.tw",8080)
            conn.request("POST","/register/stepB1.asp", params, headers) 
            response = conn.getresponse()
            data = response.read()
            soup = BeautifulSoup(data, fromEncoding='big5')
            resultRows = soup.findAll('tr', {'class': re.compile('tablecontent.')})
            
            rawDates = [re.findall('[0-9]+', tr('td')[0].string) for tr in resultRows]
            rawTimes = [tr('td')[2].string for tr in resultRows]
            
            q = Doctor.all()
            q.filter("department =", departmentName)
            results = q.fetch(100)
            doctors = [{result.id: result.name} for result in results]
            
            dates = []
            for rawDate in rawDates:
                dates += ['%(year)d-%(month)02d-%(day)02d' % 
                          {'year': int(rawDate[0]) + 1911, 
                           'month': int(rawDate[1]), 
                           'day': int(rawDate[2])}]
            
            times = []
            for rawTime in rawTimes:
                if rawTime == '上午':#.decode('big5'):
                    times += ['A']
                elif rawTime == '下午':#.decode('big5'):
                    times += ['B']
                else: #晚上
                    times += ['C']
            
            def strCat(str1, str2):
                return str1 + '-' + str2

            time = map(strCat, dates, times)
            
            ret = [
                      {'id': queryId},
                      {'name': departmentName},
                      {'doctor': doctors}, #TODO
                      {'time': time}
                  ]
        
        self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))


class Doctors(webapp.RequestHandler):
    def get(self):
        queryId = self.request.get("id")
        if queryId == '': # return all doctors
            q = Doctor.all()
            q.order("id")
            
            # The query is not executed until results are accessed.
            results = q.fetch(1000)
            ret = []
            for d in results:
                ret += [{d.id: d.name}]
        else:
            queryId = int(queryId)
            
            q = Doctor.all()
            q.filter("id =", queryId)
            results = q.fetch(1)
            try:
                result = results.pop()
            except:
                self.response.out.write(json.dumps([], ensure_ascii=False, indent=4))
                return
            
            doctorName = result.name
            headers = {
                           "User-Agent": "Mozilla/5.0",
                           "Connection": "keep-alive",
                           "Content-Type": "application/x-www-form-urlencoded"
                      }
            EmpNO = result.EmpNO
            SectNO = ''
            fromDate = datetime.date.today()
            toDate = fromDate + datetime.timedelta(7)
            
            syear = str(fromDate.year - 1911)
            smonth = '%02d' %  fromDate.month
            sday = '%02d' % fromDate.day
            eyear = str(toDate.year - 1911)
            emonth = '%02d' % toDate.month
            eday = '%02d' % toDate.day
            
            params = urllib.urlencode({
                          'syear': syear, 'smonth': smonth, 'sday': sday,
                          'eyear': eyear, 'emonth': emonth, 'eday': eday,
                          'SectNO': SectNO, 'EmpNO': EmpNO, 'isQuery': '1'
                     })
            
            conn = httplib.HTTPConnection("806.mnd.gov.tw",8080)
            conn.request("POST","/register/stepB1.asp", params, headers) 
            response = conn.getresponse()
            data = response.read()
            soup = BeautifulSoup(data, fromEncoding='big5')
            resultRows = soup.findAll('tr', {'class': re.compile('tablecontent.')})
            
            rawDates = [re.findall('[0-9]+', tr('td')[0].string) for tr in resultRows]
            rawTimes = [tr('td')[2].string for tr in resultRows]
            departmentName = unicode(resultRows[0]('td')[1].string)
            
            # find department id
            q = Department.all()
            q.filter("name =", departmentName)
            results = q.fetch(1)
            try:
                result = results.pop()
                department = [{result.id: departmentName}]
            except:
                department = [{0: departmentName}]
            
            dates = []
            for rawDate in rawDates:
                dates += ['%(year)d-%(month)02d-%(day)02d' % 
                          {'year': int(rawDate[0]) + 1911, 
                           'month': int(rawDate[1]), 
                           'day': int(rawDate[2])}]
            
            times = []
            for rawTime in rawTimes:
                if rawTime == '上午':#.decode('big5'):
                    times += ['A']
                elif rawTime == '下午':#.decode('big5'):
                    times += ['B']
                else: #晚上
                    times += ['C']
            
            def strCat(str1, str2):
                return str1 + '-' + str2

            time = map(strCat, dates, times)
            
            ret = [
                      {'id': queryId},
                      {'name': doctorName},
                      {'dept': department}, #TODO
                      {'time': time}
                  ]
        
        self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))

class Register(webapp.RequestHandler):
    def get(self):
        if self.request.get('first') == 'TRUE':
            ret = {"status": 1, 
                   "message": "You have to go to hospital in person for the first registration!"}
            self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))
            return

        lackField = []
        
        #idNo = xxxxxxxxxx
        idNo = self.request.get('id')
        if idNo == None:
            lackField += [{"id": "Identification Number"}]
        
        # birthday = 1989-09-14
        birthday = self.request.get('birthday');
        if birthday == None:
            lackField += [{"birthday": "Birthday (format: yyyy-mm-dd)"}]
            
        # deptId = 14
        deptId = self.request.get('dept')
        if deptId == None:
            lackField += [{"dept": "Department id"}]
            
        # when = '2011-05-14-A'
        when = self.request.get('time')
        if when == None:
            lackField += [{"time": "Time (format: yyyy-mm-dd-A/B/C)"}]
        
        # doctorId = 41
        doctorId = self.request.get('doctor')
        if doctorId == None:
            lackField += [{"doctor": "Doctor Id"}]
        
        if len(lackField) != 0:
            ret = {"status": 2, 
                   "message": lackField}
            self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))
            return
        
        birthday = birthday.split('-')
        birthday[0] = str(int(birthday[0])-1911)
        birthday = ''.join(birthday)
        
        headers = {
                      "User-Agent": "Mozilla/5.0",
                      "Connection": "keep-alive",
                      "Content-Type": "application/x-www-form-urlencoded"
                  }
        
        params = urllib.urlencode({
                      'HospArea': '1', 
                      'IDNo': idNo,
                      'birthyear': '',
                      'birthmonth': '',
                      'birthday': '',
                      'birthdate': birthday,
                      'Dir2': '1',
                      'LabelInfo': '',
                      'Submit1': '%ACd%AE%D6%A8%AD%A5%F7'
                 })
        
        cj = cookielib.LWPCookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        urllib2.install_opener(opener)
        request = urllib2.Request("http://806.mnd.gov.tw:8080/register/check.asp",
                                  data=params, headers=headers)
        response = opener.open(request)
        data = response.read()
        soup = BeautifulSoup(data, fromEncoding='big5')
        
        q = Department.all()
        q.filter("id =", int(deptId))
        results = q.fetch(1)
        try:
            result = results.pop()
            SectNO = result.SectNO
        except:
            ret = {"status": 1, 
                   "message": "No such dept"}
            self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))
            return
        
        td = soup.find('td', onclick=re.compile(r'window\.location="stepa2\.asp\?LabelInfo=' + SectNO + ',.*'));
        path = td['onclick'][17:-2]
        path1 = urllib.quote(path.encode("big5"), safe='@=?,')
        url = "http://806.mnd.gov.tw:8080/register/" + path1
        
        #print 'first url', url
        #path2 = urllib.unquote(path1).decode("unicode-escape")
        # output1=urllib.quote(source.encode("unicode-escape")) #先轉成unicode byte輸出 然後在urlencoe
        # output2=urllib.unquote(output1).decode("unicode-escape") #把上一步的結果urldecode回來 然後再把unicode byte轉回中文字
        
        request = urllib2.Request(url, headers=headers)
        response = opener.open(request)
        data = response.read()
        soup = BeautifulSoup(data, fromEncoding='big5')
        
        when = when.split('-')
        tzshift = datetime.timedelta(hours=8) # GMT+8
        today = (datetime.datetime.today() + tzshift).date()
        regDay = datetime.date(int(when[0]), int(when[1]), int(when[2]))
        delta = regDay - today
        delta = delta.days
        if when[3] == 'A':
            time = '1'
        elif when[3] == 'B':
            time = '2'
        else:
            time = '3'

        table = soup.find('table', {'class': 'tableborder'})
        row = table('tr')[delta]
        block = row.findAll('td', onclick=re.compile(r'window.*'))
        action = [b['onclick'] for b in block]
        match = [re.search(r'window\.location="(.*)";', a) for a in action]
        info = [m.groups()[0] for m in match]
        # path: stepa3.asp?OrderInfo=1000513,1,10,1F09,D000104,1,1
        #                            date,time,dept,room,doctor,1,1
        comp = [p.split('=')[1].split(',') for p in info]
        for c in comp:
            if c[1] == time:
                path = ','.join(c)
                break
        
        #print 'delta', delta
        #print 'row', row
        #print 'block', block
        #print 'action', action
        #print 'match', match
        #print 'info', info
        #print 'comp', comp
        #print 'path', path
        
        q = Doctor.all()
        q.filter("id =", int(doctorId))
        results = q.fetch(1)
        try:
            result = results.pop()
            EmpNO = result.EmpNO
        except:
            ret = {"status": 1, 
                   "message": "No such doctor"}
            self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))
            return
        
        
        url = "http://806.mnd.gov.tw:8080/register/stepa3.asp?OrderInfo=" + path
        #print 'second url', url
        request = urllib2.Request(url, headers=headers)
        response = opener.open(request)
        
        # Check the register number
        url = "http://806.mnd.gov.tw:8080/register/stepC1.1.asp"
        request = urllib2.Request(url, headers=headers)
        response = opener.open(request)
        data = response.read()
        soup = BeautifulSoup(data)
        table = soup.find('table', {'class': 'tableborder'})
        row = table('tr')[1]
        try:
            regNo = str(row('td')[5].string)
            ret = {"status": 0, "message": regNo}
        except:
            ret = {"status": 1, "message": -1}
        
        self.response.headers['Content-Type'] = 'text/html; charset=big5'
        self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))
        
class CancelRegister(webapp.RequestHandler):
    def get(self):
        if self.request.get('first') == 'TRUE':
            ret = {"status": 1, 
                   "message": "You have to go to hospital in person for the first registration!"}
            self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))
            return

        lackField = []
        
        #idNo = xxxxxxxxxx
        idNo = self.request.get('id')
        if idNo == None:
            lackField += [{"id": "Identification Number"}]
        
        # birthday = 1989-09-14
        birthday = self.request.get('birthday');
        if birthday == None:
            lackField += [{"birthday": "Birthday (format: yyyy-mm-dd)"}]
            
        # deptId = 14
        deptId = self.request.get('dept')
        if deptId == None:
            lackField += [{"dept": "Department id"}]
            
        # when = '2011-05-14-A'
        when = self.request.get('time')
        if when == None:
            lackField += [{"time": "Time (format: yyyy-mm-dd-A/B/C)"}]
        
        # doctorId = 41
        doctorId = self.request.get('doctor')
        if doctorId == None:
            lackField += [{"doctor": "Doctor Id"}]
        
        if len(lackField) != 0:
            ret = {"status": 1, 
                   "message": lackField}
            self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
            self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))
            return
        
        birthday = birthday.split('-')
        birthday[0] = str(int(birthday[0])-1911)
        birthday = ''.join(birthday)
        
        headers = {
                      "User-Agent": "Mozilla/5.0",
                      "Connection": "keep-alive",
                      "Content-Type": "application/x-www-form-urlencoded"
                  }
        
        params = urllib.urlencode({
                      'HospArea': '1', 
                      'IDNo': idNo,
                      'birthyear': '',
                      'birthmonth': '',
                      'birthday': '',
                      'birthdate': birthday,
                      'Dir2': '1',
                      'LabelInfo': '',
                      'Submit1': '%ACd%AE%D6%A8%AD%A5%F7'
                 })
        
        cj = cookielib.LWPCookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        urllib2.install_opener(opener)
        request = urllib2.Request("http://806.mnd.gov.tw:8080/register/check.asp",
                                  data=params, headers=headers)
        opener.open(request)
        
        url = "http://806.mnd.gov.tw:8080/register/stepC1.asp"
        request = urllib2.Request(url, headers=headers)
        response = opener.open(request)
        data = response.read()
        soup = BeautifulSoup(data, fromEncoding='big5')
        table = soup.find('table', {'class': 'tableborder'})
        row = table('tr')[1]
        action = unicode(row('td')[6]['onclick'])
        
        match = re.search(r"window\.location='(.*)';", action)
        path = match.groups()[0]
        
        url = "http://806.mnd.gov.tw:8080/register/" + path
        request = urllib2.Request(url, headers=headers)
        response = opener.open(request)
        
        # Check the register number
        url = "http://806.mnd.gov.tw:8080/register/stepC3.asp"
        request = urllib2.Request(url, headers=headers)
        response = opener.open(request)
        data = response.read()
        soup = BeautifulSoup(data)
        table = soup.find('table', {'class': 'tableborder'})
        row = table('tr')[1]
        regNo = str(row('td')[1].string)
        ret = {"status": 0, "message": regNo}
        
        self.response.headers['Content-Type'] = 'text/html; charset=big5'
        self.response.out.write(json.dumps(ret, ensure_ascii=False, indent=4))

class FetchDataHandler(webapp.RequestHandler):
    def get(self):
        # Add the task to the default queue.
        taskqueue.add(url='/fetchDataWorker')

        self.redirect('/')

application = webapp.WSGIApplication([
                                      ('/fetchDataWorker', FetchData),
                                      ('/fetchData', FetchDataHandler),
                                      ('/listDatabase', ListDatabase),
                                      ('/clearDatabase', ClearDatabase),
                                      ('/dept', Departments),
                                      ('/doctor', Doctors),
                                      ('/register', Register),
                                      ('/cancel_register', CancelRegister),
                                      ('/', Hello)
                                     ], 
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
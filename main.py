###----LIBRARIES-----####

from os import defpath
import pandas as pd
import numpy as np
import datetime as dt
import dateutil
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, render_template, request, redirect


###----ALGORITHM-----###
def uncleared_amount(d0,d1,url_sheet):
    
    # Ensuring the correct date format
    #try:
        #re.compile(r'\d\d/\d\d/\d\d\d\d$').search(d0).group()
        #re.compile(r'\d\d/\d\d/\d\d\d\d$').search(d1).group()
    
    #except Exception as e:
        #print("Error",  "Do not use any symbol aside from '/' and insert the data in the format MM/DD/YYYY: \n \n {}".format(e))
        #raise

    
    #Transforming the input
    d0 = dt.datetime.strptime(d0,'%Y-%m-%d')
    d1 = dt.datetime.strptime(d1,'%Y-%m-%d')
    
    if d0 > d1:
        #sys.exit('Error | Please,  insert a start date higher than the end date' )
        print("Error",  'Please,  insert a start date higher than the end date')
        raise
    else:
        ##########   Authorization to acess google drive and spreadsheets ########
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file("northstar-automation-key.json", scopes=scope)
            client = gspread.authorize(creds)

        except Exception as e:
            print("Error",  'Please, check the information for Google API authorization: \n {}'.format(e))
            raise

        ### ----- TRANSFORMATING INPUT DATA --- ###
    
        date_range = pd.date_range(d0 - dateutil.relativedelta.relativedelta(months = 1) ,d1, freq='MS').strftime("%B %Y").tolist()


        ### ----- OPENING  GOOGLE SPREADSHEET ----- ###
        ### We need to standardize the sheet name to get transacations from the right month
        try:

            recuring = client.open_by_url(url_sheet)
            list_df = []
            for sheet_name in date_range:
                sheet_month = recuring.worksheet(sheet_name)
                df = pd.DataFrame(data=sheet_month.get_all_records(head = 4))
                df.columns = list(map(str.strip,df.columns))
                df_trans = df[['Vendor','Current','Paid', 'Due Date']]
                list_df.append(df_trans)

        except Exception as e:
            print("Error",  'Please, check the columns of interest and the worksheet regading recurring bills: \n {}'.format(e))
            raise

        try:   
            df_trans = pd.concat(list_df)    
            df_trans.index = range(len(df_trans.index))

        except Exception as e:
            print("Error",  'Please, check the range of dates you are looking at: \n {}'.format(e))
            raise

        ### -------- DATA PREPARATION -------- ###
        # Remember: tell tiffany to remove blanck space in the column name 'Current'
        # tell tiffany to format the payment date column to full date (not the abreviation)
        # the same column for different sheets must have the same column name, considering blanck spaces between the strings

        #Column Date Payment
        try:
            df_trans['Due Date'] = df_trans['Due Date'].apply(lambda x: '' if type(x) == float else x)
            df_trans['Due Date'] = df_trans['Due Date'].apply(lambda c: '' if ';' in c else ('' if ',' in c else c)) #remove rows that has more than one date in the  column Payment Date
            df_trans = df_trans.drop(index = df_trans[df_trans['Due Date'] == ""].index, axis = 0)
            df_trans = df_trans.drop(index = df_trans[df_trans['Due Date'] == "N/A"].index, axis = 0)
            df_trans['Due Date'] = pd.to_datetime(df_trans['Due Date'], format = '%m/%d/%Y')

        except Exception as e:
            print("Error", "There is something wrong on the column Current: \n {}".format(e))
            raise

        #Column Current
        try:
            df_trans['Current'] = df_trans['Current'].apply(lambda x: x.replace('$', '').replace(',', '').replace(' ', '').replace('-', ''))
            df_trans = df_trans.drop(index = df_trans[df_trans['Current'] == "N/A"].index, axis = 0)
            df_trans = df_trans.drop(index = df_trans[df_trans['Current'] == ""].index, axis = 0)
            df_trans['Current'] = df_trans['Current'].astype(float)

        except Exception as e:
            print("Error", "There is something wrong on the column Current: \n {}".format(e))
            raise

        outcome = df_trans[(df_trans['Due Date'] >= d0) & (df_trans['Due Date'] <= d1) &  (df_trans['Paid'] != 'Y')]
        amount = outcome['Current'].sum()
        string_result = 'Total amount of $ {} bills not paid between {} and {}'.format(round(amount,2),d0.strftime('%m/%d/%Y'),d1.strftime('%m/%d/%Y'))
        print(string_result)
        
        #### ----- SETTING OUTPUT IN TABULAR FORMAT ------ #####
        
        outcome = outcome.assign(Due_Date = outcome['Due Date'].apply(lambda x: x.strftime('%m/%d/%Y'))).drop(
            columns=['Due Date'], axis = 1).rename(columns = {'Due_Date': 'Due Date'}) #.set_index('Due Date')
        outcome['Current'] = outcome['Current'].astype(str).apply(lambda x: "$ " + x) 
                
        #### ---- DISPLAYING THE OUTPUT IN A TABLE WIDGET ---- #### 
    print(outcome.sort_values(by = 'Due Date'))  
    return string_result, outcome.sort_values(by = 'Due Date')



###----FLASK APP---####
app = Flask(__name__)

# Display the table
@app.route("/table")
def table(table, header, result):
    return render_template('table.html', headings = header, data = table, result = result )

# Get the inputs from the form
@app.route("/")
@app.route("/container", methods=["GET", "POST"])
def consult():

    if request.method == 'POST':
        req = request.form

        #Getting Inputs
        url_sheet = req['url_sheet']
        start_date = req['start_date']
        end_date = req['end_date']

       
        # Running the function 
        string_result, df = uncleared_amount(start_date, end_date, url_sheet)
        header = tuple(df.columns)
        data = []
        list_of_rows = df.values.tolist()
        for row in list_of_rows:
            data.append(tuple(row))

        data = tuple(data)

        return table(data,header,string_result)
            

        return redirect(request.url)

    return render_template("container.html")


if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8080, debug=True)
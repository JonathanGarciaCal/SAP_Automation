' Set a material field
Dim objField, materialID
Set objField = session.FindById("wnd[0]/usr/ctxtRMATNR")
materialID = "MAT001"
objField.Text = materialID
objField.Press

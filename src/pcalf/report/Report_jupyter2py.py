#!/usr/bin/env python
# coding: utf-8

# In[1]:


import json
import os
import re

import sqlite3
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import igraph
from igraph import Graph, EdgeSeq
from jinja2 import Template

NTER_CMAP = {
        "Z-type":"#7ad5a3",
        "X-type":"#322f26",
        "CoBaHMA-type":"#0babc1",
        "Y-type":"#b980d1",
        "Unknown-type":"#717171"
}

def define_ccya_genotype(x):
    if x.Accession.startswith("GCA"):
        prefix="GCA" 
    elif x.Accession.startswith("GCF"):
        prefix = "GCF"
    else:
        return None
    
    if x.flag == "Calcyanin with known N-ter" or x.flag == "Calcyanin with new N-ter":
        return prefix + "+"
    return prefix+"-"

def count_genotypes(df , group):
    datas = {"ccyA+":0,"ccyA-":0}
    if group in df.columns:
        df = df.reset_index().set_index(group)
        for k in list(set(df.index)):
            #datas[k]="ccyA-"
            loc = df.loc[k]
            if isinstance(loc,pd.Series):
                loc = pd.DataFrame(loc).T
            if "ccyA+" in loc["(ccyA)"].values:                
                datas["ccyA+"]+=1
                continue
            datas["ccyA-"]+=1
        return datas
    else:
        raise KeyError(group)
        


# In[52]:


def make_genome_pie_chart(cnx):
    summary_df = pd.read_sql_query("""
        SELECT * FROM genomes as g JOIN 
        harley as h on h.Accession=g.Accession LEFT JOIN 
        summary as s on G.Accession = s.sequence_src""", 
                                   cnx , index_col="Accession").reset_index()
    #return summary_df
    summary_df.Accession = summary_df.apply(lambda x : x.Accession[0],axis=1)
    summary_df["uid"] = summary_df.apply(lambda x : x.Accession.split("_")[-1].split(".")[0], axis=1 )
    summary_df["uidv"] = summary_df.apply(lambda x : x.Accession.split("_")[-1], axis=1 )
    summary_df["(DBccyA)"] = summary_df.apply(lambda x : define_ccya_genotype(x), axis=1 )
    summary_df["(ccyA)"] = summary_df.apply(lambda x : "ccyA+" if x.flag in ["Calcyanin with known N-ter","Calcyanin with new N-ter"] else "ccyA-", axis=1 )
    summary_df = summary_df[["Organism", "uid", "uidv", "Accession", "Assembly name" , "Date" , "(ccyA)" , "sequence_accession", "flag", "nter"]]

    # We reformat the dictionnary and make a plotly-friendly dataframe.
    metrics_d = []
    for g in ["Organism", "uid" , "uidv" , "Accession"] :
        d = count_genotypes(summary_df , group = g)      
        total = len(list(summary_df[g].unique()))
        metrics_d.append(
            ("{} [{}]".format(g,total) ,"ccyA+",d["ccyA+"])
        )
        metrics_d.append(
            ("{} [{}]".format(g,total),"ccyA-",d["ccyA-"])
        )


    # We make a figure with multiple pie-chart [strain, GCA-GCF, GCA, GCF].   
    metrics_df = pd.DataFrame(metrics_d)
    metrics_df.columns = ["RedLevel","genotype","count"]
    fig = px.pie(metrics_df,values="count",names="genotype",facet_col="RedLevel",color="genotype",
            color_discrete_map=
#                 {"ccyA-":"#ffb4b4","ccyA+":"#439775","ccyA~":"orange"}
                 {"ccyA-":"#D5D5D8","ccyA+":"#88D9E6","ccyA~":"orange"}
                 
                )
    return fig

make_genome_pie_chart(cnx)


# In[4]:


def make_decision_tree_chart():
    # DECISION TREE CHART
        nr_vertices = 11
        v_label = list(map(str, range(nr_vertices)))
        G = Graph.Tree(nr_vertices, 2) # 2 stands for children number
        lay = G.layout_reingold_tilford(mode="in", root=[0])
        position = {k: lay[k] for k in range(nr_vertices)}
        Y = [lay[k][1] for k in range(nr_vertices)]
        M = max(Y)
        es = EdgeSeq(G) # sequence of edges
        E = [e.tuple for e in G.es] # list of edges
        L = len(position)
        Xn = [position[k][0] for k in range(L)]
        Yn = [2*M-position[k][1] for k in range(L)]
        Xe = []
        Ye = []
        Ec = {}
        color = "#c6587e"
        txt = "N"
        for edge in E:
            Xe=[position[edge[0]][0],position[edge[1]][0], None]
            Ye=[2*M-position[edge[0]][1],2*M-position[edge[1]][1], None]
            Ec[edge] = [Xe,Ye,color,txt]
            # we alternate the vertice color for positive and negative answer
            if color == "#48d38b":
                color = "#c6587e"
                txt = "N"
            else:
                color = "#48d38b"
                txt = "Y"
        # Nodes values
        node_txt = {
            0:"[Sequence has a significative hit against the GlyX3]<br>Does the sequence have three glycine zipper in the right order (G1|G2|G3) ?",
            1:"Does the sequence have<br>at least a G1 and G3 in this order ?",
            2:"Does the sequence have<br>a Known N-ter ?",
            3:"Does the sequence have<br>Known N-ter ?",
            4:"Does the sequence have<br>a N-ter of type Y ?",
            5:"Calcyanin with<br>new N-ter",
            6:"Calcyanin with<br>known N-ter",
            7:"Atypical gly region<br>with new N-ter",
            8:"Atypical gly region<br>with known N-ter",
            9:"Atypical gly region<br>with new N-ter",#"Calcyanin with<br>new N-ter",
            10:"Calcyanin with<br>known N-ter",
        }  

        labels = ["<b>"+txt+"</b>" if _ in [9,10,5,6] else txt for _,txt in node_txt.items()]
        decision_tree = go.Figure()
        for e,E in Ec.items():
            decision_tree.add_trace(go.Scatter(x=E[0],
                            y=E[1],
                        mode='lines',
                        line=dict(color=E[2], width=4),
                        opacity=0.5,
                        text = E[3],
                        hoverinfo="text",
        #                   hoverinfo='none'
                        ))


        decision_tree.add_trace(go.Scatter(x=Xn,
                        y=Yn,
                        mode='markers+text',
                        name='bla',
                        marker=dict(symbol='diamond',
                                        size=30,
                                        color='white',    #'#DB4551',
                                        #opacity=0.5,
                                        line=dict(color='rgb(50,50,50)', width=1)
                                        ),
                        text=labels,
                        textposition='top center',
                        hoverinfo='text',
                        opacity=1
                        ))
        decision_tree.update_xaxes(visible=False)
        decision_tree.update_yaxes(visible=False)
        decision_tree.update_layout({
        'margin':dict(l=40, r=40, b=85, t=100),
        'showlegend':False,
        'plot_bgcolor': 'rgba(0, 0, 0, 0)',
        'paper_bgcolor': 'rgba(0, 0, 0, 0)',
        'title': "Calcyanin classification decision tree.",
        'height':750,
        })
        return decision_tree
#make_decision_tree_chart()    


# # Number of cyanobacteria over time

# In[5]:


def count_genome_by_date(df , group , label):
    df.sort_values("Date",inplace=True)
    if group in df.columns:
        df = df.reset_index().set_index(group)
        df = df[~df.index.duplicated(keep="first")]
        df.reset_index(inplace=True)
        df = pd.DataFrame(df.groupby("Date").count()[group])
        df.columns=["count_by_date"]
        df["total"] = df["count_by_date"].cumsum(axis = 0)
        df["label"] = label

        return df
    
    else:
        raise KeyError(group)

def make_genome_over_time_chart(cnx):
    summary_df = pd.read_sql_query("""
        SELECT * FROM genomes as g JOIN 
        harley as h on h.Accession=g.Accession LEFT JOIN 
        summary as s on G.Accession = s.sequence_src""", 
                                   cnx , index_col="Accession").reset_index()
    summary_df.Accession = summary_df.apply(lambda x : x.Accession[0],axis=1)
    summary_df["uid"] = summary_df.apply(lambda x : x.Accession.split("_")[-1].split(".")[0], axis=1 )
    summary_df["uidv"] = summary_df.apply(lambda x : x.Accession.split("_")[-1], axis=1 )
    summary_df["(DBccyA)"] = summary_df.apply(lambda x : define_ccya_genotype(x), axis=1 )
    summary_df["(ccyA)"] = summary_df.apply(lambda x : "ccyA+" if x.flag in ["Calcyanin with known N-ter","Calcyanin with new N-ter"] else "ccyA-", axis=1 )
    summary_df = summary_df[["Organism", "uid", "uidv", "Accession", "Assembly name" , "Date" , "(ccyA)" , "sequence_accession", "flag", "nter"]]


    assembly_count_df = pd.concat(
        [count_genome_by_date(summary_df,"Organism","Strain<br>[i.e Microcystis aeruginosa PCC 9443]"),
         count_genome_by_date(summary_df,"uid","Assembly<br>[i.e XXX_<assembly>.N]"),
         count_genome_by_date(summary_df,"uidv","Version<br>[i.e XXX_<assembly>.<version>]"),     
         count_genome_by_date(summary_df,"Accession","Entry<br>[i.e <ncbi db>_<assembly>.<version>]"),
        ])

    genome_over_time = px.line(assembly_count_df.reset_index().sort_values(["Date","label"]),
                               hover_data=["count_by_date"],
                               x="Date", y="total",color="label" ,markers=True)   
    genome_over_time.update_layout(
        title="Number of entry over time",
        yaxis_title="#entries",
        xaxis_title="Date",
        legend_title="Level of redundancy",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0.1)")
    )
    return genome_over_time

#make_genome_over_time_chart(cnx)


# # Number of sequences over time

# In[6]:


def count_seq_by_date(df , group , subset = [] , label = None):
    df.sort_values("Date",inplace=True)
    if group in df.columns:
        df = df.reset_index().set_index(group)
        df = df[~df.index.duplicated(keep="first")]

        df.reset_index(inplace=True)
        df.fillna("NA",inplace=True)
        grouping_variables = ["Date"]+subset

        df = pd.DataFrame(df.groupby(grouping_variables).count()[group])
        df.columns=["count_by_date"]
        #df["total"] = df["count_by_date"].cumsum(axis = 0)
        #df["label"] = label if label else group
        return df
    else:
        raise KeyError(group)

def make_sequence_over_time_chart(cnx):
    summary_df = pd.read_sql_query("""
        SELECT * FROM genomes as g JOIN 
        harley as h on h.Accession=g.Accession JOIN 
        summary as s on G.Accession = s.sequence_src""", 
                                   cnx , index_col="Accession").reset_index()
    summary_df.Accession = summary_df.apply(lambda x : x.Accession[0],axis=1)

    assembly_count_df = count_seq_by_date(summary_df,"sequence_accession", ["flag","nter"])


    datas = []
    for flag,nter in assembly_count_df.reset_index("Date").index.unique():
        tmp = assembly_count_df.reset_index()
        tmp = tmp[(tmp.flag == flag) & (tmp.nter == nter)]
        tmp["total"] = tmp.count_by_date.cumsum(axis = 0)
        datas.append(tmp)
    assembly_count_df = pd.concat(datas)


    fig = px.line(assembly_count_df.reset_index(),x="Date", y="total",
                               color_discrete_map=NTER_CMAP,
                               hover_data=["count_by_date"],color="nter",line_dash="flag" ,markers=True)   
    fig.update_layout(
        title="Number of calcyanin by N-ter type and flag over time",
        yaxis_title="#sequences",
        xaxis_title="Date",
        legend_title="Calcyanin N-ter type and flag",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0.1)")
    )
    return fig

#make_sequence_over_time_chart(cnx)


# # Modular organization

# In[7]:


DOM_CMAP = {
        "Gly1":"#ecec13",   
        "Gly2":"#ec9d13",
        "Gly3":"#e25d3f",
        "GlyX3":"#d9d5d4"
    }
DOM_CMAP.update(NTER_CMAP)


# In[238]:


def sequence_modular_orga(rid,record,y,**kwargs):
        """
        rid : Sequence accession
        record : 
        """
        traces = []
        segments = {}
        segment_id = 0
        for _,f in record["features"].items():
            domid = f["feature_id"]     
            if domid == "N-ter":
                domid = f["feature_src"].split("|")[0]

            x = list(range(f["feature_start"],f["feature_end"],20))
            hover = [domid for _ in x]
            segments[segment_id]= (x,hover)
            segment_id+=1


        # ADD FULL SEQ TRACES
        line = dict(color='black', width=1, dash='dash')
        xlen = [0,len(record['sequence'])] #list(range(0,len(record['sequence']),len(record['sequence'])))
        traces.append(go.Scatter(x=xlen, y=[y for i in range(0,len(xlen))],
                            mode='lines',
                            name="full-seq",
                            hovertext=rid,
                            line=line,#showlegend=False,                                             
                            legendgroup="full-seq",
                            legendgrouptitle_text="full-seq",
                            opacity = 0.4,
                            #fill="none",
                            #fillcolor=None,
                            #name="second legend group",                                                            
                            )
            ) 
                
        for _,segm in segments.items():
                if segm:
                    if segm[0][0] and segm[0][1] :
                        sx,sh = segm
                        sy = [y for i in range(0,len(sx))]
                        dom = sh[0]
                        if dom in DOM_CMAP:                
                            line = dict(color=DOM_CMAP[dom],width=3)
                        else:
                            #print(dom)
                            line = dict(color='black', width=1)

                        neighbor = "NA"
                        if "nter_neighbor" in record:
                            neighbor = record["nter_neighbor"]
                        htxt = "- {}<br>- {}<br>- {}<br>- {}<br>- {} [nearest neighbor]<br>".format(
                            rid,
                            dom, 
                            record["flag"],
                            "From {} to {}".format(min(sx),max(sx)),
                            neighbor
                        )
                        customdatas = [{"seqid":rid}]
                        for i,j in kwargs.items():
                            htxt+="- {}: {}<br>".format(i,j)
                            customdatas.append({i:j})

                        traces.append(go.Scatter(
                                x=sx, y=sy,
                                mode='lines',
                                name=dom,
                                line=line,#showlegend=False,                                             
                                legendgroup=dom,
                                legendgrouptitle_text=dom,
                                text="",
                                hoverlabel=None,
                                hovertext=htxt,
                                hoveron='points+fills',
                                customdata = customdatas,                                                            
                            )
                        )    
        return traces


def make_modorg_chart(cnx):
    # Plotting modular organization
    # First we load the feature 'table'
    features_df = pd.read_sql_query("SELECT * FROM features as f JOIN summary as s on s.sequence_accession=f.sequence_id", cnx ).set_index("sequence_id")
    features_df["e-value"] = features_df.apply(lambda x : '{:0.2e}'.format(x["e-value"]),axis=1)
    features_dict = {}
    # dictionnary with sequence identifiers as keys and features as values
    for _ , sdf in features_df.groupby("sequence_id"):
        features_dict[_]=sdf.reset_index().T.to_dict()
    features_dict
    # dictionnary with sequence identifiers as keys and sequence-related information + features as values
    sequence_datas = {}

    sequence_df = pd.read_sql_query("""
        SELECT * FROM summary as s JOIN genomes as g on g.Accession = s.sequence_src
        """, cnx ).set_index("sequence_accession")
    for _ , row in sequence_df.iterrows():
        sequence_datas[_] = row.to_dict()
        sequence_datas[_]["features"]=features_dict[_]  

    # For each type of N-ter we make a modular organization chart.    
    oms_plots = {}
    for nter_type in list(set(sequence_df.nter)):
        if not nter_type:
            nter_type = "Unknown-type"
        fig = go.Figure()
        y = 1
        cpt = 0
        for rid , record in sequence_datas.items():
            if not record["nter"]:
                record["nter"] = "Unknown-type"
            if record["nter"] == nter_type:
                cpt+=1
                traces = sequence_modular_orga(rid,
                                    record,
                                    y,
                                    Organism_Name=record["Organism"],
                                    Assembly=record["sequence_src"]
                                )
                if traces:
                    for t in traces:
                        fig.add_trace(t)
                    y+=1
                cpt+=1
                leg = []
                for trace in fig['data']:
                    leg.append
                    if trace['name'] not in leg:
                        leg.append(trace['name'])
                    else:
                        trace['showlegend'] = False
            fig.update_layout(
                autosize=False,
                width=1000,
                height=10*cpt if cpt > 100 else 700,
                margin=dict(
                    l=50,
                    r=50,
                    b=100,
                    t=100,
                    pad=4
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(visible=False),
                xaxis=dict(gridcolor="rgba(0,0,0,0.1)"),
                xaxis_title="Sequence length (aa)",
                title="Modular organization [{}]".format(nter_type)
            )   
            oms = fig #.to_html().split("<body>")[1].split("</body>")[0]      
            oms_plots[nter_type] = oms
    return oms_plots


make_modorg_chart(cnx)["Z-type"]#.to_html(full_html=False,
#    div_id="Z-type-plot",
#    include_plotlyjs=False)





# In[285]:


def make_sunburst(cnx):
    sequence_df = pd.read_sql_query("""
        SELECT * FROM summary as s JOIN 
        genomes as g on g.Accession = s.sequence_src JOIN
        harley as h on h.Accession = g.Accession

        """,cnx).set_index("sequence_accession")
    sequence_df.nter.fillna("Unknown-type",inplace=True)
    sequence_df = sequence_df.groupby(
        ["Date","flag","nter","cter"]).count().reset_index() 
    sequence_df = sequence_df[["Date","flag","nter","cter","sequence_src"]]
    sequence_df.columns = ["Date","flag","nter","cter","No of sequences"]
    # We make a sunburst chart : 
    sunburst = px.sunburst(sequence_df, path=['nter', 'flag', 'cter', "Date"], 
                           values='No of sequences', 
                           color = "nter",
                           color_discrete_map=NTER_CMAP)
    sunburst.update_layout(title="No of Calcyanin.")
    return sunburst

def make_calcyanin_treemap(cnx):
    sequence_df = pd.read_sql_query("""
        SELECT * FROM summary as s JOIN 
        genomes as g on g.Accession = s.sequence_src JOIN
        harley as h on h.Accession = g.Accession

        """,cnx).set_index("sequence_accession")
    sequence_df.nter.fillna("Unknown-type",inplace=True)
    sequence_df = sequence_df[["flag","nter","cter","sequence_src"]]
    sequence_df.columns = ["flag","nter","cter","No of sequences"]
    sequence_df = sequence_df.groupby(
        ["flag","nter","cter"]).count().reset_index() 
    # We make a sunburst chart : 
    # And another one with the same kind of information : a treemap:
    treemap = px.treemap(sequence_df, path=['nter', 'flag', 'cter'], values='No of sequences',
                    color='nter',color_discrete_map = NTER_CMAP)
#    treemap.update_traces(root_color="lightgrey")
    treemap.update_layout(title="No of Calcyanin.")
    return treemap

make_calcyanin_treemap(cnx)
#make_sunburst(cnx)



# In[145]:


def make_data(cnx):
    # We convert the "strain" dataframe into a dictionnary - later  we will inject those datas into the report file using jinja2.
    DATAS = {}

    genomes_df = pd.read_sql_query("""
        SELECT * FROM harley as h  JOIN 
        genomes as g on g.Accession = h.Accession LEFT JOIN 
        checkm as c on g.Accession=c.`Bin Id` LEFT JOIN
        gtdbtk as t on g.Accession=t.`user_genome`
        """,cnx)

    genomes_df = genomes_df.fillna("NA")
    genomes_df = genomes_df.loc[:,~genomes_df.columns.duplicated()]
    genomes_df = genomes_df[['Accession', 'Assembly name','Date', 'Submitter',
       'Submission date', 'Isolate', 'TaxID', 'Organism', 'Biosample',
       'Isolation source', 'Environment (biome)', 'Geographic location',
       'Culture collection', 'Collection date', 'Sample type',
       'Completeness', 'Contamination', 'Strain heterogeneity',
       'Genome size (bp)', '# scaffolds', '# contigs',
       'N50 (scaffolds)', 'N50 (contigs)','# predicted genes',
       'classification', 'fastani_reference','fastani_ani']]
    
    ccyA_plus = []
    ccyA_minus = []
    for org , sdf in genomes_df.groupby(["Organism"]):
        sdf.index = sdf.Accession
        DATAS[org]=sdf.T.to_dict()
        for acc in sdf.index:
            seqs = pd.read_sql_query("""
                SELECT * FROM summary as s JOIN 
                ccya as c on c.sequence_id=s.sequence_accession WHERE
                s.sequence_src="{}"
                """.format(acc),cnx,index_col="sequence_id")
            seqs = seqs.fillna("NA")
            seqs = seqs.T.to_dict()            
            DATAS[org][acc]["sequences"] = seqs
            
            if seqs:
                ccyA_plus.append(org)
            else:
                ccyA_minus.append(org)
            
            for seq in seqs.keys():
                features = pd.read_sql_query("""
                    SELECT * FROM features as f WHERE
                        f.sequence_id="{}"
                """.format(seq),cnx)                
                features = features.fillna("NA")
                features.sort_values(["feature_id","e-value"],inplace=True)
                DATAS[org][acc]["sequences"][seq]["features"] = features.T.to_dict()
                hits = pd.read_sql_query("""
                    SELECT * FROM hits as f WHERE
                        f.sequence_id="{}"
                """.format(seq),cnx)
                hits = hits.fillna("NA")
                hits.sort_values(["hit_src","hit_e_value"],inplace=True)
                DATAS[org][acc]["sequences"][seq]["hits"] = hits.T.to_dict()
    
    DATAS = {i:DATAS[i] for i in list(set(ccyA_plus + ccyA_minus))}
                
                
    # we convert the dictionnary into a json object for jinja2 injection.
    json_object = json.dumps(DATAS, indent = 4)     
    return json_object , DATAS

d = make_data(cnx)


# In[ ]:





# In[276]:


workflow = """
<?xml version="1.0" encoding="UTF-8"?>
<!-- Created with Inkscape (http://www.inkscape.org/) -->
<svg version="1.1" position="absolute" viewBox="0 0 2560 1440" xmlns="http://www.w3.org/2000/svg">
 <defs>
  <clipPath id="clipPath20">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath42">
   <path d="m5.531 9.568h968.51v1061.9h-968.51z"/>
  </clipPath>
  <clipPath id="clipPath56">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath74">
   <path d="m339.61 772.79h244.39v99.905h-244.39z"/>
  </clipPath>
  <clipPath id="clipPath96">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath144">
   <path d="m339.61 491.04h244.39v99.905h-244.39z"/>
  </clipPath>
  <clipPath id="clipPath166">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath180">
   <path d="m198.28 502.57h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath190">
   <path d="m214.99 510.56h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath200">
   <path d="m183.69 491.52h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath210">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath242">
   <path d="m593.13 491.04h148.39v99.905h-148.39z"/>
  </clipPath>
  <clipPath id="clipPath256">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath324">
   <path d="m709.55 271.33h245.73v99.905h-245.73z"/>
  </clipPath>
  <clipPath id="clipPath338">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath382">
   <path d="m69.031 271.33h244.39v99.905h-244.39z"/>
  </clipPath>
  <clipPath id="clipPath404">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath442">
   <path d="m60.4 120.89h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath452">
   <path d="m77.116 128.88h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath462">
   <path d="m45.816 109.84h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath472">
   <path d="m88.569 141.26h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath482">
   <path d="m243.2 120.89h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath492">
   <path d="m259.92 128.88h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath502">
   <path d="m228.62 109.84h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath512">
   <path d="m271.37 141.26h61.403v78.926h-61.403z"/>
  </clipPath>
  <clipPath id="clipPath522">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath554">
   <path d="m988.94 290.41h924.67v456.83h-924.67z"/>
  </clipPath>
  <clipPath id="clipPath568">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath646">
   <path d="m1221.8 458.6h165.57v67.596h-165.57z"/>
  </clipPath>
  <clipPath id="clipPath660">
   <path d="m1224.2 463.6h161.18v57.596h-161.18z"/>
  </clipPath>
  <clipPath id="clipPath674">
   <path d="m1225.8 537.64h157.57v65.481h-157.57z"/>
  </clipPath>
  <clipPath id="clipPath684">
   <path d="m1219.5 538.64h170.27v63.481h-170.27z"/>
  </clipPath>
  <clipPath id="clipPath698">
   <path d="m1400 459.66h157.57v65.481h-157.57z"/>
  </clipPath>
  <clipPath id="clipPath708">
   <path d="m1393.7 460.66h170.26v63.481h-170.26z"/>
  </clipPath>
  <clipPath id="clipPath722">
   <path d="m1400 537.64h157.57v65.481h-157.57z"/>
  </clipPath>
  <clipPath id="clipPath732">
   <path d="m1400.4 533.18h156.8v74.9h-156.8z"/>
  </clipPath>
  <clipPath id="clipPath754">
   <path d="m1225.8 381.68h157.57v65.481h-157.57z"/>
  </clipPath>
  <clipPath id="clipPath764">
   <path d="m1219.5 382.68h170.26v63.481h-170.26z"/>
  </clipPath>
  <clipPath id="clipPath778">
   <path d="m1436.5 355.67h165.8v82.842h-165.8z"/>
  </clipPath>
  <clipPath id="clipPath792">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath912">
   <path d="m1314 893.99h277.88v63.481h-277.88z"/>
  </clipPath>
  <clipPath id="clipPath926">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
  <clipPath id="clipPath978">
   <path d="m1359.3 781h187.36v63.481h-187.36z"/>
  </clipPath>
  <clipPath id="clipPath992">
   <path d="m0 0h1920v1080h-1920z"/>
  </clipPath>
 </defs>
 <g transform="matrix(1.3333 0 0 -1.3333 0 1440)">
  <g clip-path="url(#clipPath20)">
   <path d="m0 1080h1920v-1080h-1920z" fill="#fff"/>
   <path d="m1069.1 1062h764.25c21.912 0 35.059 0 43.823-3.659 12.635-4.599 22.588-14.552 27.187-27.187 3.659-8.764 3.659-21.911 3.659-43.823v-145.02c0-21.912 0-35.058-3.659-43.823-4.599-12.635-14.552-22.588-27.187-27.187-8.764-3.6591-21.911-3.6591-43.823-3.6591h-764.25c-21.912 0-35.059 0-43.823 3.6591-12.635 4.5988-22.588 14.552-27.187 27.187-3.6591 8.7646-3.6591 21.912-3.6591 43.823v145.02c0 21.912 0 35.059 3.6591 43.823 4.599 12.635 14.552 22.588 27.187 27.187 8.764 3.659 21.911 3.659 43.823 3.659z" fill="#fff"/>
   <g transform="matrix(1 0 0 -1 994.47 1062)">
    <path d="m74.669 0h764.25c21.912 0 35.058 0 43.823 3.6591 12.635 4.5987 22.588 14.552 27.187 27.187 3.6591 8.7646 3.6591 21.912 3.6591 43.823v145.02c0 21.912 0 35.058-3.6591 43.823-4.5987 12.635-14.552 22.588-27.187 27.187-8.7646 3.6591-21.912 3.6591-43.823 3.6591h-764.25c-21.912 0-35.058 0-43.823-3.6591-12.635-4.5987-22.588-14.552-27.187-27.187-3.6591-8.7646-3.6591-21.912-3.6591-43.823v-145.02c0-21.912 0-35.058 3.6591-43.823 4.5987-12.635 14.552-22.588 27.187-27.187 8.7646-3.6591 21.912-3.6591 43.823-3.6591z" fill="none" stroke="#00a89d" stroke-width="8"/>
   </g>
   <path d="m110.61 1071.4h758.33c29.212 0 46.739 0 58.423-4.878 16.844-6.131 30.114-19.4 36.244-36.245 4.8782-11.684 4.8782-29.211 4.8782-58.423v-862.78c0-29.212 0-46.739-4.8782-58.423-6.1309-16.844-19.4-30.114-36.244-36.244-11.685-4.8782-29.212-4.8782-58.423-4.8782h-758.33c-29.212 0-46.739 0-58.423 4.8782-16.844 6.1309-30.114 19.4-36.244 36.244-4.8782 11.685-4.8782 29.212-4.8782 58.423v862.78c0 29.212 0 46.739 4.8782 58.423 6.1309 16.845 19.4 30.114 36.244 36.245 11.685 4.878 29.212 4.878 58.423 4.878z" fill="#fff"/>
   <g transform="matrix(1 0 0 -1 11.067 1071.4)">
    <path d="m99.546 0h758.33c29.212 0 46.739 0 58.423 4.8782 16.844 6.1309 30.114 19.4 36.244 36.244 4.8782 11.685 4.8782 29.212 4.8782 58.423v862.78c0 29.212 0 46.739-4.8782 58.423-6.1309 16.845-19.4 30.114-36.244 36.245-11.685 4.878-29.212 4.878-58.423 4.878h-758.33c-29.212 0-46.739 0-58.423-4.878-16.844-6.131-30.114-19.4-36.244-36.245-4.8782-11.684-4.8782-29.211-4.8782-58.423v-862.78c0-29.212 0-46.739 4.8782-58.423 6.1309-16.844 19.4-30.114 36.244-36.244 11.685-4.8782 29.212-4.8782 58.423-4.8782z" fill="none" stroke="#7c43cb" stroke-width="8"/>
   </g>
  </g>
  <g clip-path="url(#clipPath42)">
   <g transform="translate(479.11 528.72)">
    <text transform="scale(1,-1)" fill="#ffffff" font-family="'Helvetica Neue'" font-size="32px" font-weight="500" xml:space="preserve"><tspan x="0" y="0">A</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath56)">
   <path d="m432.69 1045c-0.3212 0-0.585-0.257-0.585-0.578v-75.77c0-0.3212 0.2638-0.5783 0.585-0.5783h58.233c0.3213-1e-4 0.585 0.2571 0.585 0.5783v55.355c0 0.112-0.0912 0.206-0.206 0.206h-19.99c-0.3212 0-0.5849 0.257-0.5849 0.578v20.003c-1e-4 0.113-0.0913 0.206-0.2061 0.206zm40.717-0.306c-0.072-0.03-0.1263-0.1-0.1263-0.193v-17.157c0-0.321 0.2638-0.579 0.585-0.579h17.144c0.185 0 0.276 0.223 0.1462 0.353l-17.523 17.53c-0.0649 0.064-0.154 0.076-0.2261 0.046zm-30.532-27.521h37.865c0.0936 0 0.1728-0.079 0.1728-0.173v-3.49c0-0.094-0.0792-0.173-0.1728-0.173h-37.865c-0.0936 0-0.1728 0.079-0.1728 0.173v3.49c0 0.094 0.0792 0.173 0.1728 0.173zm0-9.559h37.865c0.0936 0 0.1728-0.08 0.1728-0.173v-3.49c0-0.094-0.0792-0.166-0.1728-0.166h-37.865c-0.0936 0-0.1728 0.072-0.1728 0.166v3.49c0 0.093 0.0792 0.173 0.1728 0.173zm0-9.5597h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5592h37.865c0.0936 0 0.1728-0.0793 0.1728-0.1729v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1729 0.1728 0.1729z" fill="#a092d8"/>
   <g transform="translate(429.03 934.02)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 8.8800001 24.99 39.990002 49.439999" y="0">fasta</tspan></text>
   </g>
   <path d="m371.39 872.69h180.84c6.7224 0 10.756 0 13.445-1.1226 3.8764-1.4109 6.9299-4.4644 8.3408-8.3408 1.1226-2.689 1.1226-6.7224 1.1226-13.445v-54.089c0-6.7224 0-10.756-1.1226-13.445-1.4109-3.8763-4.4644-6.9299-8.3408-8.3408-2.6889-1.1226-6.7224-1.1226-13.445-1.1226h-180.84c-6.7223 0-10.756 0-13.445 1.1226-3.8764 1.4109-6.93 4.4645-8.3408 8.3408-1.1226 2.689-1.1226 6.7224-1.1226 13.445v54.089c0 6.7224 0 10.756 1.1226 13.445 1.4108 3.8764 4.4644 6.9299 8.3408 8.3408 2.6889 1.1226 6.7224 1.1226 13.445 1.1226z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath74)">
   <g transform="translate(375.26 830.61)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="32px" font-weight="500" xml:space="preserve"><tspan x="0 18.368 46.208 74.047997 90.655998 108.448 126.24 136.92799 154.72" y="0">hmmsearch</tspan></text>
   </g>
   <g transform="translate(382.38 791.61)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="32px" font-weight="500" xml:space="preserve"><tspan x="0 19.552 36.16 59.264 87.711998 116.16 136.32001" y="0">pyHMMER</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath96)">
   <g transform="matrix(1 0 0 -1 461.81 923.67)">
    <path d="m0 0 4.2578e-6 34.18 2.4914e-7 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m453.41 889.49 8.4-16.8 8.4 16.8z"/>
   <path d="m230.17 861.2c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.0721-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1463 0.3524l-17.523 17.53c-0.0649 0.0649-0.1539 0.0764-0.226 0.0466zm-30.533-27.521h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1729-0.1729-0.1729h-37.865c-0.0936 0-0.1728 0.0793-0.1728 0.1729v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728z" fill="#a092d8"/>
   <g transform="translate(219.57 751.88)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 22.77 29.43 44.43 62.759998" y="0">GlyX3</tspan></text>
    <text transform="matrix(1,0,0,-1,79.44,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(222.33 715.88)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 21.66 47.790001" y="0">HMM</tspan></text>
   </g>
   <g transform="matrix(1 0 0 -1 288.99 822.74)">
    <path d="M 0,3.36169e-6 42.68968,0 h 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m331.68 814.34 16.8 8.4-16.8 8.4z"/>
   <path d="m432.69 721.81c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.0721-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1462 0.3524l-17.523 17.53c-0.0649 0.0649-0.154 0.0764-0.226 0.0466zm-30.533-27.521h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1729-0.1729-0.1729h-37.865c-0.0936 0-0.1728 0.0793-0.1728 0.1729v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728z" fill="#a092d8"/>
   <g transform="matrix(1 0 0 -1 461.81 772.79)">
    <path d="m2.4415e-5 0-1.6369e-5 34.18-9.5781e-7 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m453.41 738.61 8.4-16.8 8.4 16.8z"/>
   <path d="m371.39 590.95h180.84c6.7224 0 10.756 0 13.445-1.1226 3.8764-1.4109 6.9299-4.4645 8.3408-8.3408 1.1226-2.689 1.1226-6.7224 1.1226-13.445v-54.089c0-6.7224 0-10.756-1.1226-13.445-1.4109-3.8764-4.4644-6.9299-8.3408-8.3408-2.6889-1.1226-6.7224-1.1226-13.445-1.1226h-180.84c-6.7223 0-10.756 0-13.445 1.1226-3.8764 1.4109-6.93 4.4644-8.3408 8.3408-1.1226 2.6889-1.1226 6.7224-1.1226 13.445v54.089c0 6.7224 0 10.756 1.1226 13.445 1.4108 3.8763 4.4644 6.9299 8.3408 8.3408 2.6889 1.1226 6.7224 1.1226 13.445 1.1226z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath144)">
   <g transform="translate(375.26 548.87)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="32px" font-weight="500" xml:space="preserve"><tspan x="0 18.368 46.208 74.047997 90.655998 108.448 126.24 136.92799 154.72" y="0">hmmsearch</tspan></text>
   </g>
   <g transform="translate(382.38 509.87)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="32px" font-weight="500" xml:space="preserve"><tspan x="0 19.552 36.16 59.264 87.711998 116.16 136.32001" y="0">pyHMMER</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath166)">
   <g transform="matrix(1 0 0 -1 461.81 644.88)">
    <path d="m0 0 1.7416e-5 37.137 9.3791e-7 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m453.41 607.75 8.4-16.8 8.4 16.8z"/>
  </g>
  <g clip-path="url(#clipPath180)">
   <path d="m199.86 580.5c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.0721-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1463 0.3524l-17.523 17.53c-0.0649 0.0649-0.1539 0.0764-0.226 0.0466zm-30.532-27.521h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1729-0.1729-0.1729h-37.865c-0.0936 0-0.1729 0.0793-0.1729 0.1729v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath190)">
   <path d="m216.58 588.49c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3213 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.206 0.206h-19.99c-0.3212 0-0.5849 0.2572-0.5849 0.5784v20.003c-1e-4 0.1127-0.0913 0.2061-0.2061 0.2061zm40.717-0.3058c-0.072-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.185 0 0.276 0.2226 0.1462 0.3524l-17.523 17.53c-0.0649 0.0649-0.154 0.0764-0.2261 0.0466zm-30.532-27.521h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1729-0.1728-0.1729h-37.865c-0.0936 0-0.1728 0.0793-0.1728 0.1729v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath200)">
   <path d="m185.28 569.45c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.2061-0.2061 0.2061h-19.989c-0.3212 0-0.585 0.2571-0.585 0.5783v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.072-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1463 0.3524l-17.523 17.53c-0.0648 0.0648-0.1539 0.0763-0.226 0.0465zm-30.532-27.521h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1729-0.1729-0.1729h-37.865c-0.0936 0-0.1729 0.0793-0.1729 0.1729v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5592h37.865c0.0936-1e-4 0.1729-0.0793 0.1729-0.1729v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1729 0.1729 0.1729z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath210)">
   <g transform="matrix(1 0 0 -1 291.69 540.75)">
    <path d="m0 0.11959 41.992-0.088428" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m331.7 532.32 16.782 8.4353-16.818 8.3646z"/>
   <g transform="translate(166.7 442.73)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 22.77 29.43 44.43 52.200001 68.879997 77.220001 93.900002 102.24 118.92" y="0">Gly(1,2,3)</tspan></text>
    <text transform="matrix(1,0,0,-1,126.69,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(185.59 406.73)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 21.66 47.790001 73.919998" y="0">HMMs</tspan></text>
   </g>
   <path d="m625.58 590.95h83.506c6.7224 0 10.756 0 13.445-1.1226 3.8763-1.4109 6.9299-4.4645 8.3408-8.3408 1.1226-2.689 1.1226-6.7224 1.1226-13.445v-54.089c0-6.7224 0-10.756-1.1226-13.445-1.4109-3.8764-4.4645-6.9299-8.3408-8.3408-2.689-1.1226-6.7224-1.1226-13.445-1.1226h-83.506c-6.7224 0-10.756 0-13.445 1.1226-3.8763 1.4109-6.9299 4.4644-8.3408 8.3408-1.1226 2.6889-1.1226 6.7224-1.1226 13.445v54.089c0 6.7224 0 10.756 1.1226 13.445 1.4109 3.8763 4.4645 6.9299 8.3408 8.3408 2.689 1.1226 6.7224 1.1226 13.445 1.1226z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath242)">
   <g transform="translate(620.5 529.87)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="32px" font-weight="500" xml:space="preserve"><tspan x="0 19.552 27.264 45.056 61.664001 72.32" y="0">blastP</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath256)">
   <path d="m803.29 579.46c-0.3212 0-0.585-0.2571-0.585-0.5783v-75.77c0-0.3212 0.2638-0.5783 0.585-0.5783h58.233c0.3212 0 0.585 0.2571 0.585 0.5783v55.355c0 0.1128-0.0912 0.2061-0.2061 0.2061h-19.989c-0.3212 0-0.585 0.2571-0.585 0.5784v20.003c0 0.1127-0.0912 0.206-0.2061 0.206zm40.717-0.3058c-0.0721-0.0297-0.1263-0.1002-0.1263-0.1927v-17.158c0-0.3212 0.2638-0.5783 0.585-0.5783h17.144c0.1851 0 0.276 0.2226 0.1463 0.3523l-17.523 17.53c-0.0649 0.0649-0.1539 0.0763-0.226 0.0465zm-30.532-27.521h37.865c0.0936 0 0.1729-0.0793 0.1729-0.1729v-3.49c0-0.0936-0.0793-0.1728-0.1729-0.1728h-37.865c-0.0936 0-0.1729 0.0792-0.1729 0.1728v3.49c0 0.0936 0.0793 0.1729 0.1729 0.1729zm0-9.5593h37.865c0.0936 0 0.1729-0.0793 0.1729-0.1729v-3.49c0-0.0936-0.0793-0.1661-0.1729-0.1661h-37.865c-0.0936 0-0.1729 0.0725-0.1729 0.1661v3.49c0 0.0936 0.0793 0.1729 0.1729 0.1729zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728z" fill="#a092d8"/>
   <g transform="translate(785.75 472.84)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 20.01 36.689999 53.91 76.650002" y="0">Known</tspan></text>
    <text transform="matrix(1,0,0,-1,93.33,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(797.97 436.84)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 21.66 33.330002 42.779999 58.889999" y="0">N-ter</tspan></text>
   </g>
   <g transform="matrix(1 0 0 -1 731.99 540.99)">
    <path d="m70.716 0-55.916 1.2921e-6" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m748.79 549.39-16.8-8.4 16.8-8.4z"/>
   <g transform="matrix(1 0 0 -1 491.51 682.37)">
    <path d="m0 0c105.01 5.3734 165.12 30.369 180.33 74.987l0.4162 1.9582" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m663.63 605.63 11.709-14.687 4.7239 18.179z"/>
   <path d="m432.69 359.75c-0.3212 0-0.585-0.2571-0.585-0.5783v-75.77c0-0.3212 0.2638-0.5783 0.585-0.5783h58.233c0.3213 0 0.585 0.2571 0.585 0.5783v55.355c0 0.1127-0.0912 0.2061-0.206 0.2061h-19.99c-0.3212 0-0.5849 0.2571-0.5849 0.5783v20.003c-1e-4 0.1128-0.0913 0.2061-0.2061 0.2061zm40.717-0.3058c-0.072-0.0298-0.1263-0.1002-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5783 0.585-0.5783h17.144c0.185 0 0.276 0.2225 0.1462 0.3523l-17.523 17.53c-0.0649 0.0649-0.154 0.0763-0.2261 0.0465zm-30.532-27.521h37.865c0.0936 0 0.1728-0.0793 0.1728-0.1729v-3.49c0-0.0936-0.0792-0.1728-0.1728-0.1728h-37.865c-0.0936 0-0.1728 0.0792-0.1728 0.1728v3.49c0 0.0936 0.0792 0.1729 0.1728 0.1729zm0-9.5593h37.865c0.0936 0 0.1728-0.0793 0.1728-0.1729v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1729 0.1728 0.1729zm0-9.5593h37.865c0.0936 0 0.1728-0.0793 0.1728-0.1729v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0937 0.0792 0.1729 0.1728 0.1729zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0937-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728z" fill="#a092d8"/>
   <g transform="translate(403.74 254.6)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 17.219999 33.330002 49.439999 58.889999 75.57 85.019997 101.13" y="0">Features</tspan></text>
   </g>
   <path d="m432.69 180.18c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.0721-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1462 0.3523l-17.523 17.53c-0.0649 0.0649-0.154 0.0764-0.226 0.0466zm-30.533-27.521h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1729-0.1729-0.1729h-37.865c-0.0936 0-0.1728 0.0793-0.1728 0.1729v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728z" fill="#a092d8"/>
   <g transform="translate(397.61 54.873)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 19.440001 36.119999 61.709999 87.300003 103.41 113.4" y="0">Summary</tspan></text>
   </g>
   <g transform="matrix(1 0 0 -1 461.81 244.25)">
    <path d="m1.2803e-5 0-9.4457e-6 47.274-3.9962e-7 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m453.41 196.98 8.4-16.8 8.4 16.8z"/>
   <g transform="matrix(1 0 0 -1 491.51 321.28)">
    <path d="m0 0 212.77 2.1901e-6" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m702.28 312.88 16.8 8.4-16.8 8.4z"/>
   <path d="m741.99 371.23h180.84c6.7224 0 10.756 0 13.445-1.1226 3.8764-1.4108 6.93-4.4644 8.3409-8.3408 1.1226-2.6889 1.1226-6.7224 1.1226-13.445v-54.089c0-6.7223 0-10.756-1.1226-13.445-1.4109-3.8764-4.4645-6.93-8.3409-8.3408-2.6889-1.1226-6.7223-1.1226-13.445-1.1226h-180.84c-6.7224 0-10.756 0-13.445 1.1226-3.8764 1.4108-6.9299 4.4644-8.3408 8.3408-1.1226 2.6889-1.1226 6.7224-1.1226 13.445v54.089c0 6.7223 0 10.756 1.1226 13.445 1.4109 3.8764 4.4644 6.93 8.3408 8.3408 2.6889 1.1226 6.7224 1.1226 13.445 1.1226z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath324)">
   <g transform="translate(777.88 309.65)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="32px" font-style="italic" font-weight="500" xml:space="preserve"><tspan x="0 23.712 43.264 62.816002 80.608002 91.264" y="0">Update</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath338)">
   <g transform="matrix(1 0 0 -1 832.41 426.52)">
    <path d="m5.8268e-6 0-4.0562e-6 38.488-2.1078e-7 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m824.01 388.03 8.4-16.8 8.4 16.8z"/>
   <path d="m803.29 180.18c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.0721-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1463 0.3523l-17.523 17.53c-0.0649 0.0649-0.1539 0.0764-0.226 0.0466zm-30.532-27.521h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1729-0.1729-0.1729h-37.865c-0.0936 0-0.1729 0.0793-0.1729 0.1729v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728z" fill="#a092d8"/>
   <g transform="translate(774.06 69.946)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 21.66 39.450001 57.240002 73.349998 82.800003 98.910004 116.7" y="0">Updated </tspan></text>
    <text transform="matrix(1,0,0,-1,125.04,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(797.97 33.946)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 21.66 33.330002 42.779999 58.889999" y="0">N-ter</tspan></text>
    <text transform="matrix(1,0,0,-1,68.88,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="matrix(1 0 0 -1 832.41 271.33)">
    <path d="m0 0 1.0267e-5 74.351 2.7617e-7 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m824.01 196.98 8.4-16.8 8.4 16.8z"/>
   <path d="m100.81 371.23h180.84c6.7223 0 10.756 0 13.445-1.1226 3.8764-1.4108 6.93-4.4644 8.3408-8.3408 1.1226-2.6889 1.1226-6.7224 1.1226-13.445v-54.089c0-6.7223 0-10.756-1.1226-13.445-1.4108-3.8764-4.4644-6.93-8.3408-8.3408-2.6889-1.1226-6.7224-1.1226-13.445-1.1226h-180.84c-6.7224 0-10.756 0-13.445 1.1226-3.8764 1.4108-6.9299 4.4644-8.3408 8.3408-1.1226 2.6889-1.1226 6.7224-1.1226 13.445v54.089c0 6.7223 0 10.756 1.1226 13.445 1.4109 3.8764 4.4644 6.93 8.3408 8.3408 2.689 1.1226 6.7224 1.1226 13.445 1.1226z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath382)">
   <g transform="translate(136.7 329.15)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="32px" font-style="italic" font-weight="500" xml:space="preserve"><tspan x="0 23.712 43.264 62.816002 80.608002 91.264" y="0">Update</tspan></text>
   </g>
   <g transform="translate(122.19 290.15)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="32px" font-style="italic" font-weight="500" xml:space="preserve"><tspan x="0 9.4720001 18.368 29.024 46.816002 58.655998 76.447998 87.103996 94.816002 110.816 128.608" y="0">(Iterative)</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath404)">
   <g transform="matrix(1 0 0 -1 304.56 321.28)">
    <path d="m127.55 0-112.75 1.5896e-6" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m321.36 329.68-16.8-8.4 16.8-8.4z"/>
   <g transform="matrix(1 0 0 -1 82.484 541.49)">
    <path d="m85.922 0c-101.88 6.1976-113.16 58.632-33.828 157.3l1.2751 1.5423" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m128.1 378.83 17.179-7.5956-4.2308 18.3z"/>
   <g transform="matrix(1 0 0 -1 48.717 807.49)">
    <path d="m180.87 0c-203.38 110-235.24 251.11-95.577 423.33l1.2856 1.5452" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m127.56 378.78 17.202-7.5422-4.2877 18.287z"/>
   <g transform="translate(53.434 54.873)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 21.66 47.790001 73.919998" y="0">HMMs</tspan></text>
   </g>
   <g transform="translate(240.69 54.873)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 26.129999 45.57 65.010002" y="0">MSAs</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath442)">
   <path d="m61.985 198.81c-0.32121 0-0.58499-0.2572-0.58499-0.5784v-75.77c0-0.3212 0.26378-0.5784 0.58499-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.09118 0.2061-0.20605 0.2061zm40.717-0.3058c-0.072-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1463 0.3524l-17.523 17.53c-0.0648 0.0649-0.1539 0.0764-0.226 0.0466zm-30.533-27.521h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1729-0.1728-0.1729h-37.865c-0.0936 0-0.17284 0.0793-0.17284 0.1729v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath452)">
   <path d="m78.701 206.81c-0.32121 0-0.58499-0.2572-0.58499-0.5784v-75.77c0-0.3212 0.26378-0.5784 0.58499-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.0721-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2637-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1462 0.3523l-17.523 17.53c-0.0649 0.0649-0.154 0.0764-0.226 0.0466zm-30.533-27.521h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c1e-4 -0.0936-0.0792-0.1729-0.1728-0.1729h-37.865c-0.0936 0-0.17284 0.0793-0.17284 0.1729v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c1e-4 -0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c1e-4 -0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c1e-4 -0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath462)">
   <path d="m47.401 187.76c-0.32122 0-0.58499-0.2572-0.58499-0.5784v-75.77c0-0.3212 0.26378-0.5784 0.58499-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.32122 1e-4 -0.58499 0.2572-0.58499 0.5784v20.003c-1e-5 0.1127-0.09121 0.2061-0.20608 0.2061zm40.717-0.3058c-0.07206-0.0298-0.12631-0.1003-0.12631-0.1928v-17.158c-1e-5 -0.3212 0.26378-0.5784 0.58499-0.5784h17.144c0.185 0 0.276 0.2226 0.1462 0.3524l-17.523 17.53c-0.06488 0.0648-0.15396 0.0763-0.22602 0.0465zm-30.533-27.521h37.865c0.0936 0 0.17284-0.0792 0.17284-0.1728v-3.49c1e-5 -0.0936-0.07924-0.1729-0.17284-0.1729h-37.865c-0.0936 0-0.17284 0.0793-0.17284 0.1729v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5593h37.865c0.0936 0 0.17284-0.0792 0.17284-0.1728v-3.49c1e-5 -0.0936-0.07924-0.1662-0.17284-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5593h37.865c0.0936 0 0.17284-0.0792 0.17284-0.1728v-3.49c1e-5 -0.0936-0.07924-0.1662-0.17284-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1728 0.17284 0.1728zm0-9.5592h37.865c0.0936-1e-4 0.17284-0.0793 0.17284-0.1729v-3.49c1e-5 -0.0936-0.07924-0.1662-0.17284-0.1662h-37.865c-0.0936 0-0.17284 0.0726-0.17284 0.1662v3.49c0 0.0936 0.07924 0.1729 0.17284 0.1729z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath472)">
   <path d="m90.154 219.19c-0.32122 0-0.58499-0.2571-0.58499-0.5783v-75.77c0-0.3212 0.26377-0.5783 0.58499-0.5783h58.233c0.3212 0 0.585 0.2571 0.585 0.5783v55.355c0 0.1128-0.0912 0.2061-0.2061 0.2061h-19.989c-0.3212 0-0.585 0.2571-0.585 0.5783v20.003c0 0.1127-0.0912 0.206-0.206 0.206zm40.717-0.3058c-0.072-0.0297-0.1263-0.1002-0.1263-0.1927v-17.158c0-0.3212 0.2638-0.5783 0.585-0.5783h17.144c0.1851 0 0.2761 0.2226 0.1463 0.3523l-17.523 17.53c-0.0649 0.0649-0.154 0.0763-0.2261 0.0465zm-30.532-27.521h37.865c0.0936 0 0.1728-0.0793 0.1728-0.1729v-3.49c0-0.0936-0.0792-0.1728-0.1728-0.1728h-37.865c-0.0936 0-0.1728 0.0792-0.1728 0.1728v3.49c-1e-4 0.0936 0.0792 0.1729 0.1728 0.1729zm0-9.5593h37.865c0.0936 0 0.1728-0.0793 0.1728-0.1729v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c-1e-4 0.0936 0.0792 0.1729 0.1728 0.1729zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.4901c0-0.0936-0.0792-0.1661-0.1728-0.1661h-37.865c-0.0936 0-0.1728 0.0725-0.1728 0.1661v3.4901c-1e-4 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c-1e-4 0.0936 0.0792 0.1728 0.1728 0.1728z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath482)">
   <path d="m244.79 198.81c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.0721-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1463 0.3524l-17.523 17.53c-0.0649 0.0649-0.1539 0.0764-0.226 0.0466zm-30.532-27.521h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1729-0.1729-0.1729h-37.865c-0.0936 0-0.1729 0.0793-0.1729 0.1729v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath492)">
   <path d="m261.51 206.81c-0.3212 0-0.5849-0.2572-0.5849-0.5784v-75.77c0-0.3212 0.2637-0.5784 0.5849-0.5784h58.233c0.3213 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.206 0.206h-19.989c-0.3213 0-0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.0721-0.0298-0.1264-0.1003-0.1264-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.185 0 0.276 0.2226 0.1462 0.3523l-17.523 17.53c-0.0649 0.0649-0.154 0.0764-0.226 0.0466zm-30.533-27.521h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1729-0.1728-0.1729h-37.865c-0.0936 0-0.1728 0.0793-0.1728 0.1729v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath502)">
   <path d="m230.21 187.76c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3212 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.2061 0.206h-19.989c-0.3212 1e-4 -0.585 0.2572-0.585 0.5784v20.003c0 0.1127-0.0912 0.2061-0.2061 0.2061zm40.717-0.3058c-0.072-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.1851 0 0.276 0.2226 0.1463 0.3524l-17.523 17.53c-0.0648 0.0648-0.1539 0.0763-0.226 0.0465zm-30.532-27.521h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1729-0.1728-0.1729h-37.865c-0.0936 0-0.1729 0.0793-0.1729 0.1729v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5592h37.865c0.0936-1e-4 0.1728-0.0793 0.1728-0.1729v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1729 0.1729 0.1729z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath512)">
   <path d="m272.96 219.19c-0.3212 0-0.585-0.2571-0.585-0.5783v-75.77c0-0.3212 0.2638-0.5783 0.585-0.5783h58.233c0.3212 0 0.585 0.2571 0.585 0.5783v55.355c0 0.1128-0.0912 0.2061-0.2061 0.2061h-19.989c-0.3212 0-0.585 0.2571-0.585 0.5783v20.003c0 0.1127-0.0912 0.206-0.2061 0.206zm40.717-0.3058c-0.072-0.0297-0.1263-0.1002-0.1263-0.1927v-17.158c0-0.3212 0.2638-0.5783 0.585-0.5783h17.144c0.1851 0 0.276 0.2226 0.1463 0.3523l-17.523 17.53c-0.0648 0.0649-0.1539 0.0763-0.226 0.0465zm-30.532-27.521h37.865c0.0936 0 0.1729-0.0793 0.1729-0.1729v-3.49c0-0.0936-0.0793-0.1728-0.1729-0.1728h-37.865c-0.0936 0-0.1729 0.0792-0.1729 0.1728v3.49c0 0.0936 0.0793 0.1729 0.1729 0.1729zm0-9.5593h37.865c0.0936 0 0.1729-0.0793 0.1729-0.1729v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1729 0.1729 0.1729zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.4901c0-0.0936-0.0793-0.1661-0.1729-0.1661h-37.865c-0.0936 0-0.1729 0.0725-0.1729 0.1661v3.4901c0 0.0936 0.0793 0.1728 0.1729 0.1728zm0-9.5593h37.865c0.0936 0 0.1729-0.0792 0.1729-0.1728v-3.49c0-0.0936-0.0793-0.1662-0.1729-0.1662h-37.865c-0.0936 0-0.1729 0.0726-0.1729 0.1662v3.49c0 0.0936 0.0793 0.1728 0.1729 0.1728z" fill="#a092d8"/>
  </g>
  <g clip-path="url(#clipPath522)">
   <g transform="matrix(1 0 0 -1 138.86 271.33)">
    <path d="m22.532 0-13.915 23.298-1.0277 1.7204" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m140.26 252.33-1.4026-18.73 15.826 10.116z"/>
   <g transform="matrix(1 0 0 -1 219.83 271.33)">
    <path d="m0 0 13.249 23.142 0.99596 1.7392" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m225.79 244.01 15.637-10.406-1.0573 18.753z"/>
   <g transform="translate(48.709 1010.9)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" font-weight="bold" xml:space="preserve"><tspan x="0 20.01 42.240002 62.790001 80.580002" y="0">PCALF</tspan></text>
   </g>
   <path d="m1094 747.24h714.5c29.212 0 46.739 0 58.423-4.8782 16.845-6.1309 30.114-19.4 36.245-36.244 4.878-11.685 4.878-29.212 4.878-58.423v-257.74c0-29.212 0-46.739-4.878-58.423-6.131-16.844-19.4-30.114-36.245-36.244-11.684-4.8782-29.211-4.8782-58.423-4.8782h-714.5c-29.212 0-46.739 0-58.424 4.8782-16.844 6.1309-30.113 19.4-36.244 36.244-4.8782 11.685-4.8782 29.212-4.8782 58.423v257.74c0 29.212 0 46.739 4.8782 58.423 6.1309 16.844 19.4 30.114 36.244 36.244 11.685 4.8782 29.212 4.8782 58.424 4.8782z" fill="#fff"/>
   <g transform="matrix(1 0 0 -1 994.47 747.24)">
    <path d="m99.546 0h714.5c29.212 0 46.739 0 58.423 4.8782 16.844 6.1309 30.114 19.4 36.244 36.244 4.8782 11.685 4.8782 29.212 4.8782 58.423v257.74c0 29.212 0 46.739-4.8782 58.423-6.1309 16.844-19.4 30.114-36.244 36.244-11.685 4.8782-29.212 4.8782-58.423 4.8782h-714.5c-29.212 0-46.739 0-58.423-4.8782-16.844-6.1309-30.114-19.4-36.244-36.244-4.8782-11.685-4.8782-29.212-4.8782-58.423v-257.74c0-29.212 0-46.739 4.8782-58.423 6.1309-16.844 19.4-30.114 36.244-36.244 11.685-4.8782 29.212-4.8782 58.423-4.8782z" fill="none" stroke="#00cb7b" stroke-width="8"/>
   </g>
  </g>
  <g clip-path="url(#clipPath554)">
   <g transform="translate(1440.6 507.24)">
    <text transform="scale(1,-1)" fill="#ffffff" font-family="'Helvetica Neue'" font-size="32px" font-weight="500" xml:space="preserve"><tspan x="0" y="0">A</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath568)">
   <path d="m1698 527.05c-0.321 0-0.584-0.2571-0.584-0.5783v-75.77c0-0.3212 0.263-0.5784 0.584-0.5784h58.234c0.321 0 0.585 0.2571 0.585 0.5784v55.355c0 0.1128-0.092 0.2061-0.206 0.2061h-19.99c-0.321 0-0.585 0.2571-0.585 0.5784v20.003c0 0.1127-0.091 0.206-0.206 0.206zm40.717-0.3057c-0.072-0.0298-0.126-0.1003-0.126-0.1928v-17.158c0-0.3212 0.264-0.5783 0.585-0.5783h17.144c0.185 0 0.276 0.2226 0.146 0.3523l-17.523 17.53c-0.065 0.0649-0.154 0.0763-0.226 0.0466zm-30.532-27.521h37.865c0.093 0 0.172-0.0793 0.172-0.1729v-3.49c0-0.0936-0.079-0.1728-0.172-0.1728h-37.865c-0.094 0-0.173 0.0792-0.173 0.1728v3.49c0 0.0936 0.079 0.1729 0.173 0.1729zm0-9.5593h37.865c0.093 0 0.172-0.0792 0.172-0.1728v-3.49c0-0.0937-0.079-0.1662-0.172-0.1662h-37.865c-0.094 0-0.173 0.0726-0.173 0.1662v3.49c0 0.0936 0.079 0.1728 0.173 0.1728zm0-9.5593h37.865c0.093 0 0.172-0.0792 0.172-0.1728v-3.49c0-0.0936-0.079-0.1662-0.172-0.1662h-37.865c-0.094 0-0.173 0.0726-0.173 0.1662v3.49c0 0.0936 0.079 0.1728 0.173 0.1728zm0-9.5593h37.865c0.093 0 0.172-0.0792 0.172-0.1728v-3.49c0-0.0936-0.079-0.1662-0.172-0.1662h-37.865c-0.094 0-0.173 0.0726-0.173 0.1662v3.49c0 0.0936 0.079 0.1728 0.173 0.1728z" fill="#49a99d"/>
   <g transform="matrix(1 0 0 -1 1697.4 527.05)">
    <path d="m0.58499 0c-0.32122 1.4891e-6 -0.58499 0.25713-0.58499 0.57834v75.77c0 0.3212 0.26378 0.57834 0.58499 0.57834h58.233c0.32122 2e-5 0.585-0.25713 0.585-0.57834v-55.355c0-0.11273-0.09121-0.20607-0.20608-0.20607h-19.989c-0.32122-1e-5 -0.58499-0.25713-0.58499-0.57835v-20.003c-1e-5 -0.11274-0.09121-0.20608-0.20608-0.20608zm40.717 0.30579c-0.07206 0.029781-0.1263 0.10025-0.1263 0.19278v17.158c-1e-5 0.32121 0.26377 0.57834 0.58499 0.57834h17.144c0.18508-1e-5 0.27601-0.22256 0.14625-0.35232l-17.523-17.53c-0.06488-0.064882-0.15396-0.076314-0.22602-0.046533zm-30.533 27.521h37.865c0.0936 0 0.17284 0.07924 0.17284 0.17284v3.49c1e-5 0.09359-0.07924 0.17283-0.17284 0.17283h-37.865c-0.0936 1e-5 -0.17283-0.07923-0.17283-0.17283v-3.49c-1e-5 -0.0936 0.07924-0.17284 0.17283-0.17284zm0 9.5593h37.865c0.0936 0 0.17284 0.07924 0.17284 0.17284v3.49c1e-5 0.09361-0.07924 0.16619-0.17284 0.16619h-37.865c-0.0936 0-0.17283-0.07259-0.17283-0.16619v-3.49c-1e-5 -0.0936 0.07924-0.17284 0.17283-0.17284zm0 9.5593h37.865c0.0936 0 0.17284 0.07924 0.17284 0.17284v3.49c1e-5 0.0936-0.07924 0.16619-0.17284 0.16619h-37.865c-0.0936 1e-5 -0.17283-0.07259-0.17283-0.16619v-3.49c-1e-5 -0.09362 0.07924-0.17284 0.17283-0.17284zm0 9.5593h37.865c0.0936 1e-5 0.17284 0.07924 0.17284 0.17284v3.49c1e-5 0.0936-0.07924 0.16619-0.17284 0.16619h-37.865c-0.0936 0-0.17283-0.07259-0.17283-0.16619v-3.49c-1e-5 -0.09362 0.07924-0.17284 0.17283-0.17284z" fill="none" stroke="#00cb7b"/>
   </g>
   <g transform="translate(1638.5 424.23)" fill="#000000" font-family="'Helvetica Neue'" font-size="24px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 14.4 28.176001 41.063999 54.408001 68.183998 88.655998 101.544 115.944" y="0">&lt;genome&gt;:</tspan></text>
    <text transform="matrix(1 0 0 -1 122.62 0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1674.5 395.23)" fill="#000000" font-family="'Helvetica Neue'" font-size="24px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 9.3360004 16.007999 34.223999 47.112 60.456001 74.232002 94.704002" y="0">- Genome</tspan></text>
    <text transform="matrix(1 0 0 -1 107.59 0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1674.5 366.23)" fill="#000000" font-family="'Helvetica Neue'" font-size="24px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 9.3360004 16.007999 33.335999 50.231998 65.783997 72.456001 78.671997 85.776001 98.664001 111.552" y="0">- CDS (faa)</tspan></text>
    <text transform="matrix(1 0 0 -1 117.77 0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1674.5 337.23)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="24px" xml:space="preserve"><tspan x="0 9.3360004 16.007999 33.335999 50.231998 65.783997 72.456001 78.671997 85.776001 99.120003 112.008" y="0">- CDS (fna)</tspan></text>
   </g>
   <path d="m1088 538.66c-13.181 0-25.587-1.8197-34.88-5.153-8.762-3.1313-13.786-7.2949-13.786-11.411 0-4.1162 5.024-8.2875 13.786-11.419 9.293-3.308 21.699-5.153 34.88-5.153 13.182 0 25.58 1.8197 34.872 5.153 8.763 3.1314 13.787 7.3028 13.787 11.419 0 4.1162-5.024 8.2796-13.787 11.411-9.292 3.308-21.69 5.153-34.872 5.153zm-49.873-20.888v-6.5341c0-9.8232 22.345-17.803 49.921-17.803 27.575 0 49.873 7.9546 49.873 17.803v6.5341c-2.146-3.6111-6.991-6.8876-14.188-9.4381-9.571-3.4091-22.249-5.2793-35.709-5.2793-13.459 0-26.163 1.8702-35.708 5.2793-7.197 2.5758-12.043 5.827-14.189 9.4381zm-0.055-13.052v-4.4665c0-9.8232 22.353-17.803 49.928-17.803 27.576 0 49.921 7.9546 49.921 17.803v4.4665c-0.656-0.808-1.411-1.594-2.32-2.3516-2.727-2.3232-6.592-4.3655-11.466-6.1079-9.697-3.4596-22.524-5.3504-36.135-5.3504s-26.445 1.8908-36.142 5.3504c-4.874 1.7424-8.706 3.7847-11.459 6.1079-0.909 0.7576-1.671 1.5435-2.327 2.3516zm0-10.985v-4.4665c0-9.8232 22.353-17.803 49.928-17.803 27.576 0 49.921 7.9545 49.921 17.803v4.4665c-0.656-0.8081-1.411-1.594-2.32-2.3516-2.727-2.3232-6.592-4.3655-11.466-6.108-9.697-3.4596-22.524-5.3503-36.135-5.3503s-26.445 1.8908-36.142 5.3503c-4.874 1.7425-8.706 3.7848-11.459 6.108-0.909 0.7576-1.671 1.5435-2.327 2.3516zm0-10.985v-4.4665c0-9.8233 22.353-17.803 49.928-17.803 27.576 0 49.921 7.9545 49.921 17.803v4.4665c-0.656-0.8081-1.411-1.5941-2.32-2.3516-2.727-2.3232-6.592-4.3655-11.466-6.108-9.697-3.4596-22.524-5.3503-36.135-5.3503s-26.445 1.8907-36.142 5.3503c-4.874 1.7425-8.706 3.7848-11.459 6.108-0.909 0.7575-1.671 1.5435-2.327 2.3516zm0-10.985v-4.4666c0-9.8232 22.353-17.803 49.928-17.803 27.576 0 49.921 7.9545 49.921 17.803v4.4666c-0.656-0.8081-1.411-1.5941-2.32-2.3517-2.727-2.3232-6.592-4.3654-11.466-6.1079-9.697-3.4596-22.524-5.3504-36.135-5.3504s-26.445 1.8908-36.142 5.3504c-4.874 1.7424-8.706 3.7848-11.459 6.1079-0.909 0.7576-1.671 1.5437-2.327 2.3517zm0-10.985v-4.4666c0-9.8232 22.353-17.803 49.928-17.803 27.576 0 49.921 7.9798 49.921 17.803v4.4666c-0.656-0.8081-1.411-1.5941-2.32-2.3517-2.727-2.3232-6.592-4.3655-11.466-6.1079-9.697-3.4596-22.524-5.3504-36.135-5.3504s-26.445 1.8908-36.142 5.3504c-4.874 1.7424-8.706 3.7847-11.459 6.1079-0.909 0.7576-1.671 1.5436-2.327 2.3517z" fill="#fff"/>
   <g transform="matrix(1 0 0 -1 1038 538.66)">
    <path d="m49.929 0c-13.182 0-25.587 1.8198-34.88 5.1531-8.7626 3.1313-13.786 7.2948-13.786 11.411 0 4.1162 5.0237 8.2875 13.786 11.419 9.2929 3.3081 21.698 5.1531 34.88 5.1531 13.182 0 25.579-1.8197 34.872-5.1531 8.7626-3.1313 13.786-7.3027 13.786-11.419 0-4.1162-5.0237-8.2796-13.786-11.411-9.2929-3.3081-21.69-5.1531-34.872-5.1531zm-49.874 20.889v6.5341c0 9.8232 22.345 17.803 49.921 17.803 27.576 0 49.874-7.9545 49.874-17.803v-6.5341c-2.1465 3.6111-6.9918 6.8876-14.189 9.4381-9.5707 3.4091-22.249 5.2793-35.709 5.2793-13.46 0-26.163-1.8702-35.709-5.2793-7.197-2.5758-12.042-5.827-14.189-9.4381zm-0.05524 13.052v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576 0 49.921-7.9545 49.921-17.803v-4.4665c-0.65658 0.80809-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3655-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611 0-26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7847-11.458-6.1079-0.90909-0.75757-1.6714-1.5435-2.328-2.3516zm0 10.985v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576-1e-5 49.921-7.9545 49.921-17.803v-4.4665c-0.65658 0.80808-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3655-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611-1e-5 -26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7847-11.458-6.1079-0.90909-0.75757-1.6714-1.5436-2.328-2.3516zm0 10.985v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576 0 49.921-7.9545 49.921-17.803v-4.4665c-0.65658 0.80808-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3654-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611-1e-5 -26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7848-11.458-6.1079-0.90909-0.75757-1.6714-1.5436-2.328-2.3516zm0 10.985v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576 0 49.921-7.9545 49.921-17.803v-4.4665c-0.65658 0.80807-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3655-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611-2e-5 -26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7848-11.458-6.1079-0.90909-0.75757-1.6714-1.5436-2.328-2.3516zm0 10.985v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576 0 49.921-7.9798 49.921-17.803v-4.4665c-0.65658 0.80806-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3655-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611-1e-5 -26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7847-11.458-6.1079-0.90909-0.75757-1.6714-1.5436-2.328-2.3516z" fill="none" stroke="#00cb7b" stroke-width="8"/>
   </g>
   <g transform="translate(1039 411.46)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 19.440001 37.23 43.889999 50.549999 60 76.110001" y="0">Sqlite3</tspan></text>
    <text transform="matrix(1,0,0,-1,92.79,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1062 375.46)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 17.219999 23.879999 30.540001" y="0">File</tspan></text>
   </g>
   <g transform="matrix(1 0 0 -1 1574.5 488.59)">
    <path d="M 122.4364,4.34831e-6 16.8,0 h -2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m1591.3 496.99-16.8-8.4 16.8-8.4z"/>
  </g>
  <g clip-path="url(#clipPath646)">
   <path d="m1249.4 521.2h110.33c6.637 0 10.62 0 13.275-1.1084 3.827-1.393 6.842-4.4079 8.235-8.2351 1.108-2.6549 1.108-6.6373 1.108-13.274v-12.36c0-6.6372 0-10.62-1.108-13.274-1.393-3.8273-4.408-6.8422-8.235-8.2352-2.655-1.1084-6.638-1.1084-13.275-1.1084h-110.33c-6.637 0-10.62 0-13.275 1.1084-3.827 1.393-6.842 4.4079-8.235 8.2352-1.108 2.6548-1.108 6.6372-1.108 13.274v12.36c0 6.6372 0 10.62 1.108 13.274 1.393 3.8272 4.408 6.8421 8.235 8.2351 2.655 1.1084 6.638 1.1084 13.275 1.1084z" fill="#7c43cb"/>
   <g transform="matrix(1 0 0 -1 1226.8 521.2)">
    <path d="m22.618 0h110.33c6.6372 0 10.62 0 13.274 1.1084 3.8273 1.393 6.8422 4.4079 8.2352 8.2351 1.1083 2.6549 1.1083 6.6372 1.1083 13.274v12.361c0 6.6372 0 10.62-1.1083 13.274-1.393 3.8273-4.4079 6.8421-8.2352 8.2351-2.6549 1.1084-6.6372 1.1084-13.274 1.1084h-110.33c-6.6372 0-10.62 0-13.274-1.1084-3.8273-1.393-6.8421-4.4079-8.2351-8.2351-1.1084-2.6549-1.1084-6.6372-1.1084-13.274v-12.361c0-6.6372 0-10.62 1.1084-13.274 1.393-3.8273 4.4079-6.8421 8.2351-8.2351 2.6549-1.1084 6.6372-1.1084 13.274-1.1084z" fill="none" stroke="#7c43cb" stroke-width="8"/>
   </g>
  </g>
  <g clip-path="url(#clipPath660)">
   <g transform="translate(1264.5 483.4)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="25px" font-weight="500" xml:space="preserve"><tspan x="0 16.674999 34.724998 51.400002 65.75" y="0">PCALF</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath674)">
   <path d="m1249.4 602.13h110.33c6.637 0 10.62 0 13.275-1.1084 3.827-1.393 6.842-4.4079 8.235-8.2351 1.108-2.6549 1.108-6.6373 1.108-13.274v-18.245c0-6.6372 0-10.62-1.108-13.274-1.393-3.8272-4.408-6.8421-8.235-8.2351-2.655-1.1084-6.638-1.1084-13.275-1.1084h-110.33c-6.637 0-10.62 0-13.275 1.1084-3.827 1.393-6.842 4.4079-8.235 8.2351-1.108 2.6549-1.108 6.6373-1.108 13.274v18.245c0 6.6372 0 10.62 1.108 13.274 1.393 3.8272 4.408 6.8421 8.235 8.2351 2.655 1.1084 6.638 1.1084 13.275 1.1084z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath684)">
   <g transform="translate(1249 561.4)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="25px" font-weight="500" xml:space="preserve"><tspan x="0 18.975 33.799999 51.849998 69.449997 79.175003 94" y="0">GTDB-TK</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath698)">
   <path d="m1423.7 524.14h110.33c6.638 0 10.62 0 13.275-1.1083 3.827-1.3931 6.842-4.4079 8.235-8.2352 1.108-2.6549 1.108-6.6372 1.108-13.274v-18.245c0-6.6372 0-10.62-1.108-13.274-1.393-3.8273-4.408-6.8421-8.235-8.2351-2.655-1.1084-6.637-1.1084-13.275-1.1084h-110.33c-6.637 0-10.62 0-13.274 1.1084-3.828 1.393-6.843 4.4078-8.236 8.2351-1.108 2.6549-1.108 6.6372-1.108 13.274v18.245c0 6.6372 0 10.62 1.108 13.274 1.393 3.8273 4.408 6.8421 8.236 8.2352 2.654 1.1083 6.637 1.1083 13.274 1.1083z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath708)">
   <g transform="translate(1424.2 483.79)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="25px" font-weight="500" xml:space="preserve"><tspan x="0 18.049999 36.099998 51.849998 69.900002 87.025002" y="0">CHECKM</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath722)">
   <path d="m1423.7 602.13h110.33c6.638 0 10.62 0 13.275-1.1084 3.827-1.393 6.842-4.4079 8.235-8.2351 1.108-2.6549 1.108-6.6373 1.108-13.274v-18.245c0-6.6372 0-10.62-1.108-13.274-1.393-3.8272-4.408-6.8421-8.235-8.2351-2.655-1.1084-6.637-1.1084-13.275-1.1084h-110.33c-6.637 0-10.62 0-13.274 1.1084-3.828 1.393-6.843 4.4079-8.236 8.2351-1.108 2.6549-1.108 6.6373-1.108 13.274v18.245c0 6.6372 0 10.62 1.108 13.274 1.393 3.8272 4.408 6.8421 8.236 8.2351 2.654 1.1084 6.637 1.1084 13.274 1.1084z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath732)">
   <g transform="translate(1448.5 576.78)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="25px" font-weight="500" xml:space="preserve"><tspan x="0 18.049999 36.099998 53.700001" y="0">NCBI</tspan></text>
   </g>
   <g transform="translate(1443.2 546.78)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="25px" font-weight="500" xml:space="preserve"><tspan x="0 22.225 37.049999 55.099998" y="0">MTDS</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath754)">
   <path d="m1249.4 446.16h110.33c6.637 0 10.62 0 13.275-1.1084 3.827-1.393 6.842-4.4078 8.235-8.2351 1.108-2.6549 1.108-6.6372 1.108-13.274v-18.245c0-6.6372 0-10.62-1.108-13.274-1.393-3.8273-4.408-6.8421-8.235-8.2352-2.655-1.1083-6.638-1.1083-13.275-1.1083h-110.33c-6.637 0-10.62 0-13.275 1.1083-3.827 1.3931-6.842 4.4079-8.235 8.2352-1.108 2.6549-1.108 6.6372-1.108 13.274v18.245c0 6.6372 0 10.62 1.108 13.274 1.393 3.8273 4.408 6.8421 8.235 8.2351 2.655 1.1084 6.638 1.1084 13.275 1.1084z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath764)">
   <g transform="translate(1275.9 405.81)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="25px" font-weight="500" xml:space="preserve"><tspan x="0 13.9 27.799999 40.775002" y="0">ccyA</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath778)">
   <g transform="translate(1458.3 385.89)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" font-style="italic" font-weight="bold" xml:space="preserve"><tspan x="0 27.209999 45 63.330002 81.660004 89.43 106.65" y="0">modules</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath792)">
   <path d="m1672.7 964.2c-0.321 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.264-0.5784 0.585-0.5784h58.233c0.321 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.091 0.2061-0.206 0.2061h-19.989c-0.321 0-0.585 0.2571-0.585 0.5783v20.003c0 0.1127-0.091 0.2061-0.206 0.2061zm40.717-0.3058c-0.072-0.0298-0.127-0.1003-0.127-0.1928v-17.158c0-0.3212 0.264-0.5784 0.585-0.5784h17.145c0.185 0 0.276 0.2226 0.146 0.3524l-17.523 17.53c-0.065 0.0648-0.154 0.0763-0.226 0.0465zm-30.533-27.521h37.865c0.094 0 0.173-0.0792 0.173-0.1728v-3.49c0-0.0936-0.079-0.1729-0.173-0.1729h-37.865c-0.093 0-0.173 0.0793-0.173 0.1729v3.49c0 0.0936 0.08 0.1728 0.173 0.1728zm0-9.5593h37.865c0.094 0 0.173-0.0792 0.173-0.1728v-3.49c0-0.0936-0.079-0.1662-0.173-0.1662h-37.865c-0.093 0-0.173 0.0726-0.173 0.1662v3.49c0 0.0936 0.08 0.1728 0.173 0.1728zm0-9.5593h37.865c0.094 0 0.173-0.0792 0.173-0.1728v-3.49c0-0.0936-0.079-0.1662-0.173-0.1662h-37.865c-0.093 0-0.173 0.0726-0.173 0.1662v3.49c0 0.0936 0.08 0.1728 0.173 0.1728zm0-9.5592h37.865c0.094-1e-4 0.173-0.0793 0.173-0.1729v-3.49c0-0.0936-0.079-0.1662-0.173-0.1662h-37.865c-0.093 0-0.173 0.0726-0.173 0.1662v3.49c0 0.0936 0.08 0.1729 0.173 0.1729z" fill="#49a99d"/>
   <g transform="matrix(1 0 0 -1 1672.1 964.2)">
    <path d="m0.58499 0c-0.32122 1.4891e-6 -0.58499 0.25713-0.58499 0.57834v75.77c0 0.3212 0.26378 0.57834 0.58499 0.57834h58.233c0.32122 2e-5 0.585-0.25713 0.585-0.57834v-55.355c0-0.11273-0.09121-0.20607-0.20608-0.20607h-19.989c-0.32122-1e-5 -0.58499-0.25713-0.58499-0.57835v-20.003c-1e-5 -0.11274-0.09121-0.20608-0.20608-0.20608zm40.717 0.30579c-0.07206 0.029781-0.1263 0.10025-0.1263 0.19278v17.158c-1e-5 0.32121 0.26377 0.57834 0.58499 0.57834h17.144c0.18508-1e-5 0.27601-0.22256 0.14625-0.35232l-17.523-17.53c-0.06488-0.064882-0.15396-0.076314-0.22602-0.046533zm-30.533 27.521h37.865c0.0936 0 0.17284 0.07924 0.17284 0.17284v3.49c1e-5 0.09359-0.07924 0.17283-0.17284 0.17283h-37.865c-0.0936 1e-5 -0.17283-0.07923-0.17283-0.17283v-3.49c-1e-5 -0.0936 0.07924-0.17284 0.17283-0.17284zm0 9.5593h37.865c0.0936 0 0.17284 0.07924 0.17284 0.17284v3.49c1e-5 0.09361-0.07924 0.16619-0.17284 0.16619h-37.865c-0.0936 0-0.17283-0.07259-0.17283-0.16619v-3.49c-1e-5 -0.0936 0.07924-0.17284 0.17283-0.17284zm0 9.5593h37.865c0.0936 0 0.17284 0.07924 0.17284 0.17284v3.49c1e-5 0.0936-0.07924 0.16619-0.17284 0.16619h-37.865c-0.0936 1e-5 -0.17283-0.07259-0.17283-0.16619v-3.49c-1e-5 -0.09362 0.07924-0.17284 0.17283-0.17284zm0 9.5593h37.865c0.0936 1e-5 0.17284 0.07924 0.17284 0.17284v3.49c1e-5 0.0936-0.07924 0.16619-0.17284 0.16619h-37.865c-0.0936 0-0.17283-0.07259-0.17283-0.16619v-3.49c-1e-5 -0.09362 0.07924-0.17284 0.17283-0.17284z" fill="none" stroke="#00cb7b"/>
   </g>
   <g transform="translate(1669.3 847.48)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 16.68 32.790001 58.380001" y="0">Yaml</tspan></text>
   </g>
   <g transform="translate(1222.3 1011.1)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" font-weight="bold" xml:space="preserve"><tspan x="0 20.01 42.240002 62.790001 80.580002 98.370003 110.58 132.81 150.60001 166.17 186.72 206.19 225.63 243.96001 263.42999 275.64001 303.95999 327.29999 348.95999 370.62 388.41 406.20001 429.54001" y="0">PCALF-DATASETS-WORKFLOW</tspan></text>
   </g>
   <g transform="translate(1100 968.54)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 13.89 30 45.540001 53.310001" y="0">TaxID</tspan></text>
    <text transform="matrix(1,0,0,-1,74.43,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1123.6 932.54)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 17.219999" y="0">or</tspan></text>
    <text transform="matrix(1,0,0,-1,27.21,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1028 896.54)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 21.66 43.32 63.869999 71.639999 79.980003 99.419998 115.53 131.64 147.75 162.75 177.75 184.41 201.63" y="0">NCBI Accession</tspan></text>
    <text transform="matrix(1,0,0,-1,218.31,0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1013.9 860.54)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 7.77 30.540001 52.200001 70.529999 85.529999 103.86 122.19 140.52 158.85001 177.17999 195.50999 213.84 222.17999 238.86" y="0">(GCX_XXXXXXX.1)</tspan></text>
   </g>
   <g transform="matrix(1 0 0 -1 1141.9 488.59)">
    <path d="m70.575 0-55.775 1.3425e-6" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m1158.7 496.99-16.8-8.4 16.8-8.4z"/>
   <path d="m1069.1 271.98h764.25c21.912 0 35.059 0 43.823-3.6591 12.635-4.5988 22.588-14.552 27.187-27.187 3.659-8.7646 3.659-21.912 3.659-43.823v-111.2c0-21.912 0-35.058-3.659-43.823-4.599-12.635-14.552-22.588-27.187-27.187-8.764-3.6591-21.911-3.6591-43.823-3.6591h-764.25c-21.912 0-35.059 0-43.823 3.6591-12.635 4.5987-22.588 14.552-27.187 27.187-3.6591 8.7646-3.6591 21.912-3.6591 43.823v111.2c0 21.912 0 35.058 3.6591 43.823 4.599 12.635 14.552 22.588 27.187 27.187 8.764 3.6591 21.911 3.6591 43.823 3.6591z" fill="#fff"/>
   <g transform="matrix(1 0 0 -1 994.47 271.98)">
    <path d="m74.669 0h764.25c21.912 0 35.058 0 43.823 3.6591 12.635 4.5987 22.588 14.552 27.187 27.187 3.6591 8.7646 3.6591 21.912 3.6591 43.823v111.2c0 21.912 0 35.058-3.6591 43.823-4.5987 12.635-14.552 22.588-27.187 27.187-8.7646 3.6591-21.912 3.6591-43.823 3.6591h-764.25c-21.912 0-35.058 0-43.823-3.6591-12.635-4.5988-22.588-14.552-27.187-27.187-3.6591-8.7646-3.6591-21.912-3.6591-43.823v-111.2c0-21.912 0-35.058 3.6591-43.823 4.5987-12.635 14.552-22.588 27.187-27.187 8.7646-3.6591 21.912-3.6591 43.823-3.6591z" fill="none" stroke="#de6493" stroke-width="8"/>
   </g>
   <g transform="translate(1334 230.04)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" font-weight="bold" xml:space="preserve"><tspan x="0 20.01 42.240002 62.790001 80.580002 98.370003 110.58 132.24001 151.67999 171.69 195.03 216.14999" y="0">PCALF-REPORT</tspan></text>
   </g>
   <path d="m1088 140.5c-13.181 0-25.587-1.8197-34.88-5.153-8.762-3.1313-13.786-7.2948-13.786-11.411 0-4.1161 5.024-8.2875 13.786-11.419 9.293-3.3081 21.699-5.1531 34.88-5.1531 13.182 0 25.58 1.8197 34.872 5.1531 8.763 3.1313 13.787 7.3027 13.787 11.419 0 4.1162-5.024 8.2797-13.787 11.411-9.292 3.308-21.69 5.1531-34.872 5.153zm-49.873-20.888v-6.5341c0-9.8232 22.345-17.803 49.921-17.803 27.575 0 49.873 7.9545 49.873 17.803v6.5341c-2.146-3.6111-6.991-6.8876-14.188-9.4381-9.571-3.4091-22.249-5.2793-35.709-5.2793-13.459 0-26.163 1.8702-35.708 5.2793-7.197 2.5758-12.043 5.827-14.189 9.4381zm-0.055-13.052v-4.4666c0-9.8232 22.353-17.803 49.928-17.803 27.576 0 49.921 7.9545 49.921 17.803v4.4666c-0.656-0.8081-1.411-1.5941-2.32-2.3517-2.727-2.3232-6.592-4.3655-11.466-6.1079-9.697-3.4596-22.524-5.3504-36.135-5.3504s-26.445 1.8908-36.142 5.3504c-4.874 1.7424-8.706 3.7847-11.459 6.1079-0.909 0.7576-1.671 1.5436-2.327 2.3517zm0-10.985v-4.4665c0-9.8232 22.353-17.803 49.928-17.803 27.576 1e-5 49.921 7.9545 49.921 17.803v4.4665c-0.656-0.80808-1.411-1.5941-2.32-2.3516-2.727-2.3232-6.592-4.3655-11.466-6.1079-9.697-3.4596-22.524-5.3504-36.135-5.3504-13.611 1e-5 -26.445 1.8908-36.142 5.3504-4.874 1.7424-8.706 3.7847-11.459 6.1079-0.909 0.75757-1.671 1.5436-2.327 2.3516zm0-10.985v-4.4665c0-9.8232 22.353-17.803 49.928-17.803 27.576 0 49.921 7.9545 49.921 17.803v4.4665c-0.656-0.80808-1.411-1.5941-2.32-2.3516-2.727-2.3232-6.592-4.3654-11.466-6.1079-9.697-3.4596-22.524-5.3504-36.135-5.3504-13.611 1e-5 -26.445 1.8908-36.142 5.3504-4.874 1.7424-8.706 3.7848-11.459 6.1079-0.909 0.75757-1.671 1.5436-2.327 2.3516zm0-10.985v-4.4665c0-9.8232 22.353-17.803 49.928-17.803 27.576 0 49.921 7.9545 49.921 17.803v4.4665c-0.656-0.80807-1.411-1.5941-2.32-2.3516-2.727-2.3232-6.592-4.3655-11.466-6.1079-9.697-3.4596-22.524-5.3504-36.135-5.3504-13.611 2e-5 -26.445 1.8908-36.142 5.3504-4.874 1.7424-8.706 3.7848-11.459 6.1079-0.909 0.75757-1.671 1.5436-2.327 2.3516zm0-10.985v-4.4665c0-9.8232 22.353-17.803 49.928-17.803 27.576-1e-5 49.921 7.9798 49.921 17.803v4.4665c-0.656-0.80806-1.411-1.5941-2.32-2.3516-2.727-2.3232-6.592-4.3655-11.466-6.1079-9.697-3.4596-22.524-5.3504-36.135-5.3504-13.611 1e-5 -26.445 1.8908-36.142 5.3504-4.874 1.7424-8.706 3.7847-11.459 6.1079-0.909 0.75757-1.671 1.5436-2.327 2.3516z" fill="#fff"/>
   <g transform="matrix(1 0 0 -1 1038 140.5)">
    <path d="m49.929 0c-13.182 0-25.587 1.8198-34.88 5.1531-8.7626 3.1313-13.786 7.2948-13.786 11.411 0 4.1162 5.0237 8.2875 13.786 11.419 9.2929 3.3081 21.698 5.1531 34.88 5.1531 13.182 0 25.579-1.8197 34.872-5.1531 8.7626-3.1313 13.786-7.3027 13.786-11.419 0-4.1162-5.0237-8.2796-13.786-11.411-9.2929-3.3081-21.69-5.1531-34.872-5.1531zm-49.874 20.889v6.5341c0 9.8232 22.345 17.803 49.921 17.803 27.576 0 49.874-7.9545 49.874-17.803v-6.5341c-2.1465 3.6111-6.9918 6.8876-14.189 9.4381-9.5707 3.4091-22.249 5.2793-35.709 5.2793-13.46 0-26.163-1.8702-35.709-5.2793-7.197-2.5758-12.042-5.827-14.189-9.4381zm-0.05524 13.052v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576 0 49.921-7.9545 49.921-17.803v-4.4665c-0.65658 0.80809-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3655-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611 0-26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7847-11.458-6.1079-0.90909-0.75757-1.6714-1.5435-2.328-2.3516zm0 10.985v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576-1e-5 49.921-7.9545 49.921-17.803v-4.4665c-0.65658 0.80808-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3655-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611-1e-5 -26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7847-11.458-6.1079-0.90909-0.75757-1.6714-1.5436-2.328-2.3516zm0 10.985v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576 0 49.921-7.9545 49.921-17.803v-4.4665c-0.65658 0.80808-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3654-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611-1e-5 -26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7848-11.458-6.1079-0.90909-0.75757-1.6714-1.5436-2.328-2.3516zm0 10.985v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576 0 49.921-7.9545 49.921-17.803v-4.4665c-0.65658 0.80807-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3655-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611-2e-5 -26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7848-11.458-6.1079-0.90909-0.75757-1.6714-1.5436-2.328-2.3516zm0 10.985v4.4665c-5.0505e-6 9.8232 22.353 17.803 49.929 17.803 27.576 0 49.921-7.9798 49.921-17.803v-4.4665c-0.65658 0.80806-1.411 1.5941-2.3201 2.3516-2.7272 2.3232-6.5925 4.3655-11.466 6.1079-9.697 3.4596-22.524 5.3504-36.135 5.3504-13.611-1e-5 -26.446-1.8908-36.143-5.3504-4.8737-1.7424-8.7058-3.7847-11.458-6.1079-0.90909-0.75757-1.6714-1.5436-2.328-2.3516z" fill="none" stroke="#00cb7b" stroke-width="8"/>
   </g>
   <g transform="matrix(1 0 0 -1 1085.7 365.14)">
    <path d="m0 0 1.6995 207.45 0.012288 1.5" fill="none" stroke="#000" stroke-dasharray="6, 6" stroke-width="3"/>
   </g>
   <path d="m1080.8 157.64 6.707-13.146 6.492 13.254z"/>
   <path d="m1521.7 127.03c-0.322 0-0.585-0.2571-0.585-0.5784v-75.77c0-0.3212 0.263-0.57834 0.585-0.57834h58.233c0.321-2e-5 0.585 0.25713 0.585 0.57834v55.355c0 0.1127-0.091 0.2061-0.206 0.2061h-19.99c-0.321 0-0.585 0.2571-0.585 0.5783v20.003c0 0.1128-0.091 0.2061-0.206 0.2061zm40.716-0.3058c-0.072-0.0298-0.126-0.1003-0.126-0.1928v-17.158c0-0.3212 0.264-0.5784 0.585-0.5784h17.144c0.185 1e-4 0.276 0.2226 0.147 0.3524l-17.524 17.53c-0.065 0.0648-0.154 0.0763-0.226 0.0465zm-30.532-27.521h37.865c0.093 0 0.173-0.07924 0.173-0.17284v-3.49c0-0.09359-0.08-0.17284-0.173-0.17284h-37.865c-0.094-1e-5 -0.173 0.07924-0.173 0.17284v3.49c0 0.0936 0.079 0.17284 0.173 0.17284zm0-9.5593h37.865c0.093 1e-5 0.173-0.07924 0.173-0.17284v-3.49c0-0.0936-0.08-0.16619-0.173-0.16619h-37.865c-0.094 0-0.173 0.07259-0.173 0.16619v3.49c0 0.0936 0.079 0.17284 0.173 0.17284zm0-9.5593h37.865c0.093-1e-5 0.173-0.07924 0.173-0.17284v-3.49c0-0.0936-0.08-0.16619-0.173-0.16619h-37.865c-0.094 0-0.173 0.0726-0.173 0.16619v3.49c0 0.09361 0.079 0.17284 0.173 0.17284zm0-9.5593h37.865c0.093-1e-5 0.173-0.07924 0.173-0.17284v-3.49c0-0.09361-0.08-0.16619-0.173-0.16619h-37.865c-0.094-1e-5 -0.173 0.07259-0.173 0.16619v3.49c0 0.09362 0.079 0.17284 0.173 0.17284z" fill="#de6493"/>
   <g transform="matrix(1 0 0 -1 1141.9 90.205)">
    <path d="m0 0 364.42 1.4629" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m1504.3 80.35 16.834 8.3325-16.766 8.4674z"/>
   <g transform="translate(1620.9 79.21)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 21.66 38.880001 65.010002 81.690002 90.029999 99.480003 115.59 133.38 150.60001 160.59" y="0">HTML report</tspan></text>
   </g>
   <g transform="matrix(1 0 0 -1 1732 896.13)">
    <path d="m0 0c72.524 84.485 75.718 208.98 9.584 373.47l-0.57178 1.3947" fill="none" stroke="#000" stroke-dasharray="6, 6" stroke-width="3"/>
   </g>
   <path d="m1735.5 525.15 1.1-14.717 11.113 9.7099z"/>
   <g transform="matrix(1 0 0 -1 1265 925.73)">
    <path d="m0 4.2575e-6 41.591-3.1401e-6" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m1304.6 917.33 16.8 8.4-16.8 8.4z"/>
   <path d="m1344 957.47h217.94c6.637 0 10.619 0 13.274-1.1084 3.828-1.393 6.842-4.4079 8.235-8.2351 1.109-2.6549 1.109-6.6372 1.109-13.274v-18.245c0-6.6372 0-10.62-1.109-13.274-1.393-3.8273-4.407-6.8422-8.235-8.2352-2.655-1.1084-6.637-1.1084-13.274-1.1084h-217.94c-6.637 0-10.619 0-13.274 1.1084-3.828 1.393-6.842 4.4079-8.235 8.2352-1.109 2.6548-1.109 6.6372-1.109 13.274v18.245c0 6.6373 0 10.62 1.109 13.274 1.393 3.8272 4.407 6.8421 8.235 8.2351 2.655 1.1084 6.637 1.1084 13.274 1.1084z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath912)">
   <g transform="translate(1330.9 916.75)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="25px" font-weight="500" xml:space="preserve"><tspan x="0 18.049999 36.099998 53.700001 60.650002 70.375 88.425003 102.8 115.325 132 148.2 163.95 178.77499 194.97501 204.7 222.75 237.10001" y="0">NCBI-DATASETS-CLI</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath926)">
   <g transform="translate(1732 959.88)" fill="#000000" font-family="'Helvetica Neue'" font-size="24px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 14.4 28.176001 41.063999 54.408001 68.183998 88.655998 101.544 115.944" y="0">&lt;genome&gt;:</tspan></text>
    <text transform="matrix(1 0 0 -1 122.62 0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1768 930.88)" fill="#000000" font-family="'Helvetica Neue'" font-size="24px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 9.3360004 16.007999 34.223999 47.112 60.456001 74.232002 94.704002" y="0">- Genome</tspan></text>
    <text transform="matrix(1 0 0 -1 107.59 0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1768 901.88)" fill="#000000" font-family="'Helvetica Neue'" font-size="24px">
    <text transform="scale(1,-1)" xml:space="preserve"><tspan x="0 9.3360004 16.007999 33.335999 50.231998 65.783997 72.456001 78.671997 85.776001 98.664001 111.552" y="0">- CDS (faa)</tspan></text>
    <text transform="matrix(1 0 0 -1 117.77 0)" xml:space="preserve"><tspan x="0" y="0"/></text>
   </g>
   <g transform="translate(1768 872.88)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="24px" xml:space="preserve"><tspan x="0 9.3360004 16.007999 33.335999 50.231998 65.783997 72.456001 78.671997 85.776001 99.120003 112.008" y="0">- CDS (fna)</tspan></text>
   </g>
   <g transform="matrix(1 0 0 -1 1584.6 925.73)">
    <path d="m0 0h70.236 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m1654.8 917.33 16.8 8.4-16.8 8.4z"/>
   <path d="m1389.2 844.48h127.43c6.638 0 10.62 0 13.275-1.1084 3.827-1.393 6.842-4.4079 8.235-8.2351 1.108-2.6549 1.108-6.6373 1.108-13.274v-18.245c0-6.6372 0-10.62-1.108-13.274-1.393-3.8272-4.408-6.8421-8.235-8.2351-2.655-1.1084-6.637-1.1084-13.275-1.1084h-127.43c-6.638 0-10.62 0-13.275 1.1084-3.827 1.393-6.842 4.4079-8.235 8.2351-1.108 2.6549-1.108 6.6373-1.108 13.274v18.245c0 6.6372 0 10.62 1.108 13.274 1.393 3.8272 4.408 6.8421 8.235 8.2351 2.655 1.1084 6.637 1.1084 13.275 1.1084z" fill="#d5d5d5"/>
  </g>
  <g clip-path="url(#clipPath978)">
   <g transform="translate(1405 804.13)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="25px" font-weight="500" xml:space="preserve"><tspan x="0 16.674999 25.025 39.849998 55.125 61.150002 75.974998 89.875" y="0">Prodigal</tspan></text>
   </g>
  </g>
  <g clip-path="url(#clipPath992)">
   <g transform="matrix(1 0 0 -1 1501.8 893.99)">
    <path d="m7.8598 8.6668 1.0077 1.1111c10.412 14.032 10.018 27.277-1.1806 39.734" fill="none" stroke="#000" stroke-dasharray="0.003, 9" stroke-dashoffset=".5" stroke-linecap="round" stroke-width="3"/>
   </g>
   <path d="m1515.6 888.65-13.756 5.3442 3.978-14.212z"/>
   <g transform="matrix(1 0 0 -1 1400.5 893.99)">
    <path d="m6.3742 9.5092-0.87391 1.2191c-7.8049 13.681-7.303 26.609 1.5047 38.784" fill="none" stroke="#000" stroke-dasharray="0.003, 9" stroke-dashoffset=".5" stroke-linecap="round" stroke-width="3"/>
   </g>
   <path d="m1411.3 879.42 2.327 14.574-13.055-6.8831z"/>
   <g transform="translate(1219 703.17)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" font-weight="bold" xml:space="preserve"><tspan x="0 20.01 42.240002 62.790001 80.580002 98.370003 110.58 131.13 153.36 175.59 198.92999 214.5 232.28999 250.62 270.06 282.26999 310.59 333.92999 355.59 377.25 395.04001 412.82999 436.17001" y="0">PCALF-ANNOTATE-WORKFLOW</tspan></text>
   </g>
   <path d="m432.69 462.64c-0.3212 0-0.585-0.2572-0.585-0.5784v-75.77c0-0.3212 0.2638-0.5784 0.585-0.5784h58.233c0.3213 0 0.585 0.2572 0.585 0.5784v55.355c0 0.1127-0.0912 0.206-0.206 0.206h-19.99c-0.3212 0-0.5849 0.2572-0.5849 0.5784v20.003c-1e-4 0.1127-0.0913 0.2061-0.2061 0.2061zm40.717-0.3058c-0.072-0.0298-0.1263-0.1003-0.1263-0.1928v-17.158c0-0.3212 0.2638-0.5784 0.585-0.5784h17.144c0.185 0 0.276 0.2226 0.1462 0.3523l-17.523 17.53c-0.0649 0.0649-0.154 0.0763-0.2261 0.0466zm-30.532-27.521h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1729-0.1728-0.1729h-37.865c-0.0936 0-0.1728 0.0793-0.1728 0.1729v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728zm0-9.5593h37.865c0.0936 0 0.1728-0.0792 0.1728-0.1728v-3.49c0-0.0936-0.0792-0.1662-0.1728-0.1662h-37.865c-0.0936 0-0.1728 0.0726-0.1728 0.1662v3.49c0 0.0936 0.0792 0.1728 0.1728 0.1728z" fill="#a092d8"/>
   <g transform="translate(373.49 414.18)">
    <text transform="scale(1,-1)" fill="#000000" font-family="'Helvetica Neue'" font-size="30px" xml:space="preserve"><tspan x="0 21.66 28.32 37.77" y="0">Hits</tspan></text>
   </g>
   <g transform="matrix(1 0 0 -1 461.81 491.04)">
    <path d="M 1.391104e-6,0 0,11.59922 v 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m453.41 479.44 8.4-16.8 8.4 16.8z"/>
   <g transform="matrix(1 0 0 -1 461.81 385.72)">
    <path d="m0 0v9.1699 2" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m453.41 376.55 8.4-16.8 8.4 16.8z"/>
   <g transform="matrix(1 0 0 -1 491.51 504.38)">
    <path d="m111.41 0-96.802 55.02-1.7424 0.99053" fill="none" stroke="#000" stroke-width="4"/>
   </g>
   <path d="m501.96 456.66-10.455-15.604 18.756 0.9985z"/>
  </g>
 </g>
</svg>

"""


# In[277]:


# And we fill the template 
def save(file,report):
        dirname = os.path.abspath(os.path.dirname(file))
        os.makedirs(dirname,exist_ok=True)
        with open( file , 'w' ) as stream:
            stream.write(report)

            
            
def render(db,templatedir,outfile,workflow):
    dbname = os.path.basename(db).split(".")[0]
    cnx = sqlite3.connect(db)
    with open(os.path.join(templatedir,'template.html')) as file_:
        template = Template(file_.read())

    oms_plots = make_modorg_chart(cnx)

    report = template.render(
        
        datas  = make_data(cnx)[0],

        css= open( os.path.join(templatedir,"template.css" )).read(),

        js = open( os.path.join(templatedir,"template.js"  )).read(),
        
        workflow = workflow,

        decision_tree = make_decision_tree_chart().to_html().split("<body>")[1].split("</body>")[0],

        sunburst = make_sunburst(cnx).to_html().split("<body>")[1].split("</body>")[0],# if sunburst else "<p style='font-style: italic;'>No calcyanin detected - No sunburst :/ </p>"  ,

        treemap = make_calcyanin_treemap(cnx).to_html().split("<body>")[1].split("</body>")[0],# if sunburst else "<p style='font-style: italic;'>No calcyanin detected - No treemap :/ </p>"  ,

        cobahma_oms = oms_plots["CoBaHMA-type"].to_html(
            full_html=False,div_id="cobahma-type-plot",include_plotlyjs=False) if "CoBaHMA-type" in oms_plots else "<p style='font-style: italic;'>No data for this kind of N-ter</p>"  ,

        x_oms = oms_plots["X-type"].to_html(
            full_html=False,div_id="x-type-plot",include_plotlyjs=False) if "X-type" in oms_plots else "<p style='font-style: italic;'>No data for this kind of N-ter</p>"  ,

        y_oms = oms_plots["Y-type"].to_html(
            full_html=False,div_id="y-type-plot",include_plotlyjs=False) if "Y-type" in oms_plots else "<p style='font-style: italic;'>No data for this kind of N-ter</p>"  ,

        z_oms = oms_plots["Z-type"].to_html(
            full_html=False,div_id="z-type-plot",include_plotlyjs=False) if "Z-type" in oms_plots else "<p style='font-style: italic;'>No data for this kind of N-ter</p>"  ,

        unknown_oms = oms_plots["Unknown-type"].to_html(
            full_html=False,div_id="unknown-type-plot",include_plotlyjs=False)  if "Unknown-type" in oms_plots else "<p style='font-style: italic;'>No data for this kind of N-ter</p>"  ,

        genome_over_time = make_genome_over_time_chart(cnx).to_html().split("<body>")[1].split("</body>")[0],

        sequence_over_time = make_sequence_over_time_chart(cnx).to_html().split("<body>")[1].split("</body>")[0],

        metrics_fig = make_genome_pie_chart(cnx).to_html(config= dict(displayModeBar = False)).split("<body>")[1].split("</body>")[0]
    )
        
    save(outfile,report)


# In[278]:


db = "../../../tests_dir/pcalf_annotate_test/pcalf.db"
cnx = sqlite3.connect(db)


# In[295]:


render(db,"./","test.html",workflow)

os.system("open test.html")


# In[ ]:



